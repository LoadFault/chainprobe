import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import pairwise

from .client import WsClient


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    index = round(p / 100 * (len(ordered) - 1))
    return ordered[index]


@dataclass
class HeadStats:
    count: int
    gaps: list[tuple[int, int]] = field(default_factory=list)
    backwards: list[tuple[int, int]] = field(default_factory=list)
    intervals: list[float] = field(default_factory=list)

    @property
    def mean_interval(self) -> float:
        return statistics.mean(self.intervals)

    @property
    def p95_interval(self) -> float:
        return percentile(self.intervals, 95)

    @property
    def jitter(self) -> float:
        return statistics.pstdev(self.intervals)


def analyze_heads(heads: list[tuple[float, int]]) -> HeadStats:
    """heads: (arrival time, block number) pairs from one subscription, in order."""
    stats = HeadStats(count=len(heads))
    for (prev_time, prev_number), (cur_time, cur_number) in pairwise(heads):
        if cur_number > prev_number + 1:
            stats.gaps.append((prev_number, cur_number))
        elif cur_number <= prev_number:
            stats.backwards.append((prev_number, cur_number))
        stats.intervals.append(round(cur_time - prev_time, 2))
    return stats


def collect_heads(
    ws: WsClient,
    subscribe_method: str,
    duration: float,
    params: list | None = None,
    stall_timeout: float = 60.0,
    on_head: Callable[[dict], None] | None = None,
) -> tuple[list[tuple[float, dict]], int]:
    """Subscribe to new heads and record them for `duration` seconds.

    Returns the received heads with their arrival time and the number of
    stalls (periods of `stall_timeout` seconds without a new head).
    """
    subscription = ws.call(subscribe_method, params)
    heads, stalls = [], 0
    deadline = time.monotonic() + duration
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            head = ws.next_event(subscription, timeout=min(stall_timeout, remaining))
        except TimeoutError:
            if time.monotonic() < deadline:
                stalls += 1
            continue
        heads.append((time.monotonic(), head))
        if on_head:
            on_head(head)
    return heads, stalls
