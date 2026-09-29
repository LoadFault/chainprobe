"""Checks of the block time and finality a network advertises, using the EVM API only."""

import pytest

from chainprobe.models import Block

pytestmark = pytest.mark.smoke

SAMPLE_BLOCKS = 50
BLOCK_TIME_TOLERANCE = 0.3


def test_block_time_matches_spec(evm, network, record_property):
    if network.block_time is None:
        pytest.skip("no advertised block time for this network")

    latest = Block.model_validate(evm.get_block("latest"))
    earlier = Block.model_validate(evm.get_block(latest.height - SAMPLE_BLOCKS))
    average = (latest.time - earlier.time) / SAMPLE_BLOCKS

    record_property("avg_block_time_s", round(average, 2))
    record_property("advertised_s", network.block_time)
    deviation = abs(average - network.block_time) / network.block_time
    assert deviation <= BLOCK_TIME_TOLERANCE, (
        f"average block time {average:.2f}s, advertised {network.block_time}s"
    )


def test_finalized_block_trails_latest_within_spec(evm, network, record_property):
    latest = Block.model_validate(evm.get_block("latest"))
    finalized_raw = evm.get_block("finalized")
    assert finalized_raw is not None, "'finalized' block tag returned null"
    finalized = Block.model_validate(finalized_raw)

    lag_blocks = latest.height - finalized.height
    lag_seconds = latest.time - finalized.time
    record_property("finality_lag_blocks", lag_blocks)
    record_property("finality_lag_s", lag_seconds)

    assert lag_blocks >= 0
    if network.max_finality_seconds is not None:
        assert lag_seconds <= network.max_finality_seconds, (
            f"finalized block is {lag_seconds}s behind latest, expected <= {network.max_finality_seconds}s"
        )
