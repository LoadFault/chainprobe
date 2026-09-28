from itertools import pairwise

import pytest

from chainprobe.client import to_int
from chainprobe.metrics import analyze_heads, collect_heads

ETH_SUBSCRIBE_WINDOW = 30


def test_eth_subscribe_new_heads_are_sequential(ws):
    heads, _ = collect_heads(ws, "eth_subscribe", ETH_SUBSCRIBE_WINDOW, params=["newHeads"])
    blocks = [head for _, head in heads]

    assert len(blocks) >= 3, f"only {len(blocks)} heads in {ETH_SUBSCRIBE_WINDOW}s"
    for prev, cur in pairwise(blocks):
        assert to_int(cur["number"]) == to_int(prev["number"]) + 1
        assert cur["parentHash"] == prev["hash"]


@pytest.mark.slow
def test_block_stream_is_stable(ws, pytestconfig, record_property):
    duration = pytestconfig.getoption("--monitor-duration")
    heads, stalls = collect_heads(ws, "chain_subscribeNewHeads", duration)
    stats = analyze_heads([(t, to_int(head["number"])) for t, head in heads])

    record_property("heads", stats.count)
    record_property("mean_interval_s", round(stats.mean_interval, 2))
    record_property("p95_interval_s", stats.p95_interval)

    assert stalls == 0
    assert not stats.gaps, f"gaps: {stats.gaps}"
    assert not stats.backwards, f"non-increasing heads: {stats.backwards}"
    assert stats.p95_interval <= stats.mean_interval * 3
