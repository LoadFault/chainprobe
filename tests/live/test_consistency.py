"""Frontier builds one Ethereum block per Substrate block, so both APIs must agree."""

import time

import pytest

from chainprobe.models import Block

FINALITY_SAMPLES = 6
FINALITY_INTERVAL = 10
MAX_FINALITY_LAG = 5


def test_evm_and_substrate_heads_match(evm, ws):
    evm_head = evm.block_number()
    substrate_head = ws.best_number()

    # the two reads are not atomic, a new block may land in between
    assert abs(substrate_head - evm_head) <= 1


def test_block_timestamp_matches_substrate_storage(evm, ws):
    # use a finalized block so both sides are guaranteed to see the same one
    block_hash = ws.finalized_hash()
    number = ws.number_of(block_hash)

    evm_block = Block.model_validate(evm.get_block(number))

    assert evm_block.time == ws.timestamp_ms(block_hash) // 1000


def test_finalized_tag_matches_substrate(evm, ws):
    evm_finalized = Block.model_validate(evm.get_block("finalized")).height

    assert abs(ws.finalized_number() - evm_finalized) <= 2


@pytest.mark.slow
def test_finality_keeps_up_with_chain(ws, record_property):
    lags, finalized = [], []
    for i in range(FINALITY_SAMPLES):
        if i:
            time.sleep(FINALITY_INTERVAL)
        best, final = ws.best_number(), ws.finalized_number()
        lags.append(best - final)
        finalized.append(final)

    record_property("finality_lags", lags)
    assert finalized[-1] > finalized[0], f"finality stuck at #{finalized[0]}"
    assert max(lags) <= MAX_FINALITY_LAG, f"lags: {lags}"
