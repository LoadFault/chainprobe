from itertools import pairwise

import pytest

from chainprobe.client import to_int
from chainprobe.metrics import collect_heads

ETH_SUBSCRIBE_WINDOW = 30


def test_eth_subscribe_new_heads_are_sequential(ws):
    stream = collect_heads(ws, "eth_subscribe", ETH_SUBSCRIBE_WINDOW, params=["newHeads"])
    blocks = [head for _, head in stream.heads]

    assert stream.closed_after is None, f"server closed the connection after {stream.closed_after:.0f}s"
    assert len(blocks) >= 3, f"only {len(blocks)} heads in {ETH_SUBSCRIBE_WINDOW}s"
    for prev, cur in pairwise(blocks):
        assert to_int(cur["number"]) == to_int(prev["number"]) + 1
        assert cur["parentHash"] == prev["hash"]


@pytest.mark.slow
def test_block_stream_is_stable(substrate, pytestconfig, record_property):
    duration = pytestconfig.getoption("--monitor-duration")
    stream = collect_heads(substrate, "chain_subscribeNewHeads", duration)
    stats = stream.stats()

    record_property("heads", stats.count)
    record_property("mean_interval_s", round(stats.mean_interval, 2))
    record_property("p95_interval_s", stats.p95_interval)

    assert stream.closed_after is None, f"server closed the connection after {stream.closed_after:.0f}s"
    assert stream.stalls == 0
    assert not stats.gaps, f"gaps: {stats.gaps}"
    assert not stats.backwards, f"non-increasing heads: {stats.backwards}"
    assert stats.p95_interval <= stats.mean_interval * 3
