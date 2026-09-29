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


@pytest.mark.parametrize("multiplier", [5, 100])
def test_get_logs_over_range_limit_is_rejected_cleanly(evm, network, multiplier):
    if network.logs_range_limit is None:
        pytest.skip("range limit of this network is unknown")

    # Rejecting a wide query is fine; hanging or crashing on it is not.
    response = logs_request(evm, network.logs_range_limit * multiplier)

    assert response.status_code < 500
    assert "error" in response.json()
    assert response.elapsed.total_seconds() < MAX_REJECT_SECONDS
