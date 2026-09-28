import time

import pytest

from chainprobe.models import Block

pytestmark = pytest.mark.smoke

MAX_BLOCK_AGE = 120
NEW_BLOCK_TIMEOUT = 30


@pytest.fixture
def latest(evm) -> Block:
    return Block.model_validate(evm.get_block("latest"))


def test_chain_id_matches_network(evm, network):
    if network.chain_id is None:
        pytest.skip("no expected chain id for this network")
    assert int(evm.call("eth_chainId"), 16) == network.chain_id


def test_net_version_matches_chain_id(evm):
    assert evm.call("net_version") == str(int(evm.call("eth_chainId"), 16))


def test_latest_block_is_fresh(latest):
    age = time.time() - latest.time
    assert -30 < age < MAX_BLOCK_AGE, f"latest block #{latest.height} is {age:.0f}s old"


def test_parent_hash_links_to_previous_block(evm, latest):
    previous = Block.model_validate(evm.get_block(latest.height - 1))
    assert latest.parentHash == previous.hash


def test_block_by_hash_matches_block_by_number(evm, latest):
    by_hash = Block.model_validate(evm.call("eth_getBlockByHash", [latest.hash, False]))
    assert by_hash == latest


def test_chain_produces_new_blocks(evm):
    start = evm.block_number()
    deadline = time.monotonic() + NEW_BLOCK_TIMEOUT
    while time.monotonic() < deadline:
        if evm.block_number() > start:
            return
        time.sleep(1)
    pytest.fail(f"no new block after #{start} in {NEW_BLOCK_TIMEOUT}s")


def test_gas_price_is_positive(evm):
    assert int(evm.call("eth_gasPrice"), 16) > 0
