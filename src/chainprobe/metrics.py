import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import pairwise

from websockets.exceptions import ConnectionClosed

from .client import WsClient, to_int


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

    @classmethod
    def merge(cls, parts: list["HeadStats"]) -> "HeadStats":
        """Combine stats of separate connections without treating a reconnect as a gap."""
        return cls(
            count=sum(part.count for part in parts),
            gaps=[gap for part in parts for gap in part.gaps],
            backwards=[pair for part in parts for pair in part.backwards],
            intervals=[interval for part in parts for interval in part.intervals],
        )


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


@dataclass
class HeadStream:
    heads: list[tuple[float, dict]] = field(default_factory=list)
    stalls: int = 0
    closed_after: float | None = None

    def stats(self) -> HeadStats:
        return analyze_heads([(arrival, to_int(head["number"])) for arrival, head in self.heads])


def collect_heads(
    ws: WsClient,
    subscribe_method: str,
    duration: float,
    params: list | None = None,
    stall_timeout: float = 60.0,
    on_head: Callable[[dict], None] | None = None,
) -> HeadStream:
    """Subscribe to new heads and record them for `duration` seconds.

    A stall is a period of `stall_timeout` seconds without a new head.
    If the server drops the connection, collection stops and `closed_after`
    holds the connection's lifetime in seconds.
    """
    started = time.monotonic()
    subscription = ws.call(subscribe_method, params)
    stream = HeadStream()
    deadline = started + duration
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            head = ws.next_event(subscription, timeout=min(stall_timeout, remaining))
        except TimeoutError:
            if time.monotonic() < deadline:
                stream.stalls += 1
            continue
        except ConnectionClosed:
            stream.closed_after = time.monotonic() - started
            break
        stream.heads.append((time.monotonic(), head))
        if on_head:
            on_head(head)
    return stream


@dataclass
class Pause:
    from_block: int
    to_block: int
    seconds: int


def find_pauses(samples: list[tuple[int, int]], block_time: float, factor: float = 3) -> list[Pause]:
    """Find windows where the chain produced blocks much slower than advertised.

    samples: (block number, timestamp) pairs taken every N blocks, in order.
    A window is a pause when it took more than `factor` times the expected time.
    """
    pauses = []
    for (prev_number, prev_time), (number, timestamp) in pairwise(samples):
        expected = (number - prev_number) * block_time
        if timestamp - prev_time > expected * factor:
            pauses.append(Pause(prev_number, number, timestamp - prev_time))
    return pauses
