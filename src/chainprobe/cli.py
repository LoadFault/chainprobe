import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

from .client import open_ws, to_int
from .config import NETWORKS, resolve_network
from .metrics import analyze_heads, collect_heads

LIVE_TESTS = Path(__file__).resolve().parents[2] / "tests" / "live"


def add_network_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--network", default="orbinum", choices=list(NETWORKS))
    parser.add_argument("--rpc", help="EVM JSON-RPC URL (overrides the preset)")
    parser.add_argument("--wss", help="Substrate WebSocket URL (overrides the preset)")
    parser.add_argument("--chain-id", type=int, help="expected EVM chain id")


def run_checks(args: argparse.Namespace) -> int:
    report = args.report or f"reports/{args.network}_{datetime.now():%Y%m%d_%H%M}.html"
    pytest_args = [
        str(LIVE_TESTS),
        "-v",
        "--network",
        args.network,
        f"--html={report}",
        "--self-contained-html",
    ]
    for option in ("rpc", "wss", "chain_id"):
        value = getattr(args, option)
        if value is not None:
            pytest_args += [f"--{option.replace('_', '-')}", str(value)]
    if args.quick:
        pytest_args += ["-m", "not slow"]
    return pytest.main(pytest_args)


def run_monitor(args: argparse.Namespace) -> int:
    network = resolve_network(args.network, args.rpc, args.wss, args.chain_id)
    print(f"Watching {network.wss} for {args.duration}s")

    def show(head: dict) -> None:
        print(f"  {time.strftime('%H:%M:%S')}  #{to_int(head['number'])}")

    with open_ws(network.wss) as ws:
        heads, stalls = collect_heads(ws, "chain_subscribeNewHeads", args.duration, on_head=show)

    stats = analyze_heads([(t, to_int(head["number"])) for t, head in heads])
    if stats.count < 2:
        print("Not enough heads received")
        return 1

    print(f"\nheads: {stats.count}, stalls: {stalls}")
    print(
        f"interval: mean {stats.mean_interval:.2f}s, p95 {stats.p95_interval}s, "
        f"max {max(stats.intervals)}s, jitter {stats.jitter:.2f}s"
    )
    print(f"gaps: {stats.gaps or 'none'}, non-increasing: {stats.backwards or 'none'}")
    return 1 if stalls or stats.gaps or stats.backwards else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="chainprobe", description="Health checks for Substrate + EVM networks"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="run the test suite and write an HTML report")
    add_network_args(check)
    check.add_argument("--quick", action="store_true", help="skip slow tests")
    check.add_argument("--report", help="HTML report path")
    check.set_defaults(func=run_checks)

    monitor = commands.add_parser("monitor", help="watch the block stream in real time")
    add_network_args(monitor)
    monitor.add_argument("--duration", type=int, default=300)
    monitor.set_defaults(func=run_monitor)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
