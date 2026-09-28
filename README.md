# chainprobe

[![ci](https://github.com/loadfault/chainprobe/actions/workflows/ci.yml/badge.svg)](https://github.com/loadfault/chainprobe/actions/workflows/ci.yml)
[![nightly](https://github.com/loadfault/chainprobe/actions/workflows/nightly.yml/badge.svg)](https://github.com/loadfault/chainprobe/actions/workflows/nightly.yml)

API tests and health checks for Substrate + EVM (Frontier) networks, written with pytest.

The suite talks to a live network the way wallets, dApps and indexers do and checks that
the answers are correct, consistent between the EVM and Substrate APIs, and fast.
Everything is read-only and rate-limited to 2 requests per second by default.
The default target is the [Orbinum](https://orbinum.network) testnet.

## What is tested

| File | What it covers |
|------|----------------|
| `test_evm_rpc.py` | chain id, block schema (pydantic), freshness, parent-hash chain, block by hash vs by number, block production, gas price |
| `test_rpc_errors.py` | JSON-RPC error codes for unknown methods, invalid params and malformed JSON; batch requests |
| `test_logs.py` | `eth_getLogs` inside and beyond the node's block-range limit |
| `test_consistency.py` | EVM vs Substrate: head height, block timestamp from `Timestamp::Now` storage, finalized block, finality lag |
| `test_subscriptions.py` | `eth_subscribe newHeads` continuity; stability of the Substrate head stream over time |
| `test_performance.py` | p95 RPC latency after warm-up |

Markers: `smoke` (fast RPC checks), `slow` (watch the network for a minute or more), `perf`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Running

With pytest directly:

```bash
pytest tests/live                          # full suite against Orbinum
pytest tests/live -m smoke                 # quick RPC checks only
pytest tests/live -m "not slow" --html=report.html --self-contained-html
pytest tests/live --rpc https://rpc.example.org --wss wss://rpc.example.org --chain-id 1284
pytest tests/unit                          # helpers, no network needed
```

Or through the CLI:

```bash
chainprobe check                 # run the live suite, write an HTML report to reports/
chainprobe check --quick         # skip slow tests
chainprobe monitor --duration 600
```

`monitor` prints every new block as it arrives and ends with interval statistics,
gaps and stalls. It exits with code 1 if the stream had problems.

## Project layout

```
src/chainprobe/
  client.py     EvmClient (requests) and WsClient (websockets) for JSON-RPC
  models.py     pydantic model of an EVM block
  metrics.py    percentiles and head-stream analysis
  config.py     network presets
  cli.py        check / monitor commands
tests/
  conftest.py   command-line options and client fixtures
  live/         tests against a real network
  unit/         tests of the helpers
```

## CI

- `ci.yml` runs ruff and the unit tests on every push.
- `nightly.yml` runs the live suite against Orbinum every night and uploads the HTML report as an artifact.

## Results: Orbinum testnet, 2026-09-26

Node `Orbinum Node 0.2.0-77675d05a89`, 55–56 peers, measured from Poznań, Poland.

| Area | Result |
|------|--------|
| Block time | mean 5.98 s, p95 6.4 s, max 8.44 s, jitter 0.43 s (101 heads in 10 min, no gaps) |
| Finality | 2–3 blocks behind best (~12–18 s), advancing on every sample |
| EVM ↔ Substrate | identical head height and block timestamps; EVM `finalized` tag matches Substrate |
| RPC latency | p50 42 ms, p95 45 ms after warm-up, no errors |
| JSON-RPC errors | correct codes for unknown method, invalid params and malformed JSON; batch supported |

Notes for builders:

- `eth_getLogs` is capped at 1024 blocks per request (~1.7 h of history at 6 s blocks).
  Wider ranges are rejected quickly with a clear error, so indexers should paginate.
- The first requests on a new connection take 110–190 ms versus ~42 ms afterwards
  (TCP + TLS setup). Reuse connections in clients.

## License

MIT
