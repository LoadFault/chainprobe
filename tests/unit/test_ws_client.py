import json

import pytest

from chainprobe.client import WsClient


class FakeConnection:
    """Answers JSON-RPC requests from a dict of method -> result or error."""

    def __init__(self, responses: dict):
        self.responses = responses
        self._pending: list[str] = []

    def send(self, raw: str) -> None:
        request = json.loads(raw)
        reply = {"jsonrpc": "2.0", "id": request["id"]}
        response = self.responses.get(request["method"])
        if response is None:
            reply["error"] = {"code": -32601, "message": "method not found"}
        else:
            reply["result"] = response
        self._pending.append(json.dumps(reply))

    def recv(self, timeout: float) -> str:
        return self._pending.pop(0)


@pytest.mark.parametrize(
    ("responses", "expected"),
    [
        pytest.param({"rpc_methods": {"methods": ["chain_getHeader", "eth_call"]}}, True, id="substrate"),
        pytest.param({"rpc_methods": {"methods": ["eth_call", "eth_subscribe"]}}, False, id="no-chain-api"),
        pytest.param({}, False, id="evm-only"),
    ],
)
def test_is_substrate(responses, expected):
    assert WsClient(FakeConnection(responses)).is_substrate() is expected
