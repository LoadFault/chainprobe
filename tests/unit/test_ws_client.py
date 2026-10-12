import json

import pytest
from websockets.exceptions import ConnectionClosedError

from chainprobe.client import WsClient, to_int
from chainprobe.metrics import HeadStats, analyze_heads, collect_heads


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


class DroppingConnection:
    """Confirms a subscription, pushes some heads, then loses the connection."""

    def __init__(self, numbers: list[int]):
        self.replies = [json.dumps({"jsonrpc": "2.0", "id": 1, "result": "0xsub"})]
        self.replies += [
            json.dumps({"params": {"subscription": "0xsub", "result": {"number": hex(n)}}}) for n in numbers
        ]

    def send(self, raw: str) -> None:
        pass

    def recv(self, timeout: float) -> str:
        if not self.replies:
            raise ConnectionClosedError(None, None)
        return self.replies.pop(0)


def test_collect_heads_stops_when_server_drops_connection():
    stream = collect_heads(WsClient(DroppingConnection([10, 11, 12])), "eth_subscribe", duration=5)

    assert [to_int(head["number"]) for _, head in stream.heads] == [10, 11, 12]
    assert stream.closed_after is not None
    assert stream.closed_after < 5


def test_merged_stats_do_not_count_reconnect_as_gap():
    before = analyze_heads([(0.0, 100), (1.0, 101)])
    after = analyze_heads([(9.0, 108), (10.0, 109)])

    merged = HeadStats.merge([before, after])

    assert merged.count == 4
    assert merged.gaps == []
    assert merged.intervals == [1.0, 1.0]
