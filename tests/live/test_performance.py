import pytest

from chainprobe.metrics import percentile

WARMUP = 3
SAMPLES = 30
P95_LIMIT_MS = 800


@pytest.mark.perf
def test_rpc_latency_p95(evm, record_property):
    # The first requests pay for TCP and TLS setup, so they are not measured.
    for _ in range(WARMUP):
        evm.request("eth_blockNumber")

    timings = []
    for _ in range(SAMPLES):
        response = evm.request("eth_blockNumber")
        assert response.status_code == 200
        timings.append(response.elapsed.total_seconds() * 1000)

    p50, p95 = percentile(timings, 50), percentile(timings, 95)
    record_property("p50_ms", round(p50, 1))
    record_property("p95_ms", round(p95, 1))
    assert p95 < P95_LIMIT_MS, f"p95 {p95:.0f}ms (p50 {p50:.0f}ms)"
