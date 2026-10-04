"""Checks of the block time and finality a network advertises, using the EVM API only."""

import pytest

from chainprobe.metrics import find_pauses
from chainprobe.models import Block

SAMPLE_BLOCKS = 50
BLOCK_TIME_TOLERANCE = 0.3
LOOKBACK_SECONDS = 24 * 60 * 60
SAMPLE_STEP = 60


@pytest.mark.smoke
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


@pytest.mark.smoke
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


@pytest.mark.slow
def test_no_block_production_pauses_in_last_day(evm, network, record_property):
    # Sampling every N-th block keeps this to a few hundred requests for a whole day;
    # a window that took far longer than N blocks should means production stalled inside it.
    if network.block_time is None:
        pytest.skip("no advertised block time for this network")

    latest = evm.block_number()
    lookback = int(LOOKBACK_SECONDS / network.block_time)
    numbers = range(max(0, latest - lookback), latest + 1, SAMPLE_STEP)
    samples = [(n, Block.model_validate(evm.get_block(n)).time) for n in numbers]

    pauses = find_pauses(samples, network.block_time)
    record_property("pauses", [f"#{p.from_block}-#{p.to_block}: {p.seconds}s" for p in pauses])
    assert not pauses, f"block production stalled: {pauses}"
