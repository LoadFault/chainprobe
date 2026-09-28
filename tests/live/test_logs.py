import pytest

pytestmark = pytest.mark.smoke

MAX_REJECT_SECONDS = 2


def logs_request(evm, span: int):
    latest = evm.block_number()
    return evm.request("eth_getLogs", [{"fromBlock": hex(latest - span), "toBlock": hex(latest)}])


@pytest.mark.parametrize("span", [100, 1000])
def test_get_logs_within_range_limit(evm, span):
    response = logs_request(evm, span)

    assert response.status_code == 200
    assert isinstance(response.json()["result"], list)


@pytest.mark.parametrize("span", [5_000, 100_000])
def test_get_logs_over_range_limit_is_rejected_cleanly(evm, span):
    # Rejecting a wide query is fine; hanging or crashing on it is not.
    response = logs_request(evm, span)

    assert response.status_code < 500
    assert "error" in response.json()
    assert response.elapsed.total_seconds() < MAX_REJECT_SECONDS
