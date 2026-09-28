import itertools
import json
import time
from collections.abc import Iterator
from contextlib import contextmanager

import requests
from websockets.sync.client import ClientConnection, connect

# twox128("Timestamp") + twox128("Now"): storage key of the block timestamp on any Substrate chain
TIMESTAMP_NOW_KEY = "0xf0c365c3cf59d671eb72da0e7a4113c49f1f0515f462cdcf84e0f1d6045dfcbb"


class RpcError(Exception):
    def __init__(self, method: str, error: dict):
        super().__init__(f"{method} failed: {error}")
        self.code = error.get("code")
        self.message = error.get("message")


def to_int(hex_value: str) -> int:
    return int(hex_value, 16)


def decode_u64(hex_value: str) -> int:
    """Substrate stores integers in SCALE encoding: little-endian bytes."""
    return int.from_bytes(bytes.fromhex(hex_value.removeprefix("0x")), "little")


class EvmClient:
    """Ethereum JSON-RPC over HTTP with a simple rate limit."""

    def __init__(self, url: str, rps: float = 2.0, timeout: float = 15.0):
        self.url = url
        self.timeout = timeout
        self.min_interval = 1 / rps if rps > 0 else 0
        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"
        self._ids = itertools.count(1)
        self._last_request = 0.0

    def close(self) -> None:
        self.session.close()

    def post(self, body: str) -> requests.Response:
        wait = self._last_request + self.min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()
        return self.session.post(self.url, data=body, timeout=self.timeout)

    def request(self, method: str, params: list | None = None) -> requests.Response:
        payload = {"jsonrpc": "2.0", "id": next(self._ids), "method": method, "params": params or []}
        return self.post(json.dumps(payload))

    def call(self, method: str, params: list | None = None):
        response = self.request(method, params)
        response.raise_for_status()
        body = response.json()
        if "error" in body:
            raise RpcError(method, body["error"])
        return body["result"]

    def block_number(self) -> int:
        return to_int(self.call("eth_blockNumber"))

    def get_block(self, block: int | str = "latest") -> dict | None:
        tag = hex(block) if isinstance(block, int) else block
        return self.call("eth_getBlockByNumber", [tag, False])


class WsClient:
    """JSON-RPC over WebSocket, used for Substrate methods and subscriptions.

    A subscription pushes messages on the same socket we use for requests,
    so notifications that arrive while waiting for a response are queued.
    """

    def __init__(self, connection: ClientConnection, timeout: float = 15.0):
        self.ws = connection
        self.timeout = timeout
        self._ids = itertools.count(1)
        self._queue: list[dict] = []

    def call(self, method: str, params: list | None = None):
        request_id = next(self._ids)
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or []}
        self.ws.send(json.dumps(payload))
        while True:
            message = json.loads(self.ws.recv(timeout=self.timeout))
            if message.get("id") == request_id:
                if "error" in message:
                    raise RpcError(method, message["error"])
                return message["result"]
            self._queue.append(message)

    def next_event(self, subscription_id: str, timeout: float) -> dict:
        """Wait for the next notification of a subscription. Raises TimeoutError."""
        deadline = time.monotonic() + timeout
        while True:
            if self._queue:
                message = self._queue.pop(0)
            else:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"no event for {timeout}s")
                message = json.loads(self.ws.recv(timeout=remaining))
            params = message.get("params", {})
            if params.get("subscription") == subscription_id:
                return params["result"]

    def best_number(self) -> int:
        return to_int(self.call("chain_getHeader")["number"])

    def finalized_hash(self) -> str:
        return self.call("chain_getFinalizedHead")

    def number_of(self, block_hash: str) -> int:
        return to_int(self.call("chain_getHeader", [block_hash])["number"])

    def finalized_number(self) -> int:
        return self.number_of(self.finalized_hash())

    def timestamp_ms(self, block_hash: str) -> int:
        return decode_u64(self.call("state_getStorage", [TIMESTAMP_NOW_KEY, block_hash]))


@contextmanager
def open_ws(url: str, timeout: float = 15.0) -> Iterator[WsClient]:
    with connect(url, open_timeout=timeout, max_size=2**22) as connection:
        yield WsClient(connection, timeout)
