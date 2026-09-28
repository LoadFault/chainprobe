import json

import pytest

pytestmark = pytest.mark.smoke


@pytest.mark.parametrize(
    ("method", "params", "expected_code"),
    [
        ("chainprobe_unknownMethod", [], -32601),
        ("eth_getBalance", ["0xnot-an-address", "latest"], -32602),
        ("eth_getBlockByNumber", ["not-a-block", False], -32602),
    ],
    ids=["unknown-method", "invalid-address", "invalid-block-tag"],
)
def test_invalid_request_returns_json_rpc_error(evm, method, params, expected_code):
    response = evm.request(method, params)

    assert response.status_code < 500
    assert response.json()["error"]["code"] == expected_code


def test_malformed_json_returns_parse_error(evm):
    response = evm.post('{"jsonrpc": "2.0", "method": ')

    assert response.status_code < 500
    assert response.json()["error"]["code"] == -32700


def test_batch_request_returns_every_response(evm):
    batch = [
        {"jsonrpc": "2.0", "id": i, "method": method, "params": []}
        for i, method in enumerate(["eth_chainId", "eth_blockNumber", "net_version"], start=1)
    ]
    response = evm.post(json.dumps(batch))

    assert response.status_code == 200
    assert sorted(item["id"] for item in response.json()) == [1, 2, 3]
