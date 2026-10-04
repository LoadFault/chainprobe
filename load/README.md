# Load test

Stepped load test of an EVM JSON-RPC endpoint with [k6](https://k6.io).

**Run it only against endpoints whose operators agreed to the test, within the limits they set.**

## Install k6

```bash
winget install k6          # Windows
brew install k6            # macOS
```

## Run

```bash
k6 run --no-usage-report \
  -e RPC_URL=https://rpc-1.testnet.orbinum.io \
  -e STEPS=5,10,25,50 \
  load/rpc_load.js
```

| Variable | Default | Meaning |
|----------|---------|---------|
| `RPC_URL` | required | endpoint under test |
| `STEPS` | `5,10,25` | request rates per second; the first is the warm-up rate, the last is held |
| `WARMUP` | `5m` | time at the first step |
| `STEP_DURATION` | `2m` | time at each intermediate step |
| `HOLD` | `5m` | time at the last step |
| `MAX_P95_MS` | `2000` | abort when overall p95 latency goes above this |
| `MAX_ERROR_RATE` | `0.05` | abort when the share of failed requests goes above this |
| `BREAKER_LIMIT` | `10` | abort after this many failed or slow requests in a row on one VU |

A request counts as failed on a non-200 status or a JSON-RPC `error` in the body.
Requests carry the `LoadFault-chainprobe` User-Agent so operators can find them in their logs.

## Traffic

Read-only calls in roughly the mix a dApp frontend produces:
`eth_blockNumber` 30%, `eth_getBlockByNumber` 25%, `eth_getBalance` 20%, `eth_call` 10%,
`eth_getLogs` (latest block) 10%, `eth_chainId` 5%.

## Output

A per-step table is printed at the end and saved to `load-summary.txt`; the full k6 summary goes to `load-summary.json`:

```
Load test of https://rpc.example.org
     5 req/s   p50    41 ms   p95    44 ms   p99    60 ms   max    120 ms   errors 0.00%   requests 1512
    10 req/s   ...
```

## Stop conditions

k6 thresholds abort the run when overall p95 or error rate crosses the limits (evaluated after the first minute).
Thresholds look at the whole run, so a sudden collapse late in the test would trip them slowly;
the per-VU circuit breaker covers that case and stops the test within seconds.
