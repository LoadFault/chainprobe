// Stepped load test of an EVM JSON-RPC endpoint.
// Every parameter comes from env so the agreed limits never live in code:
//   k6 run -e RPC_URL=https://rpc.example.org -e STEPS=5,10,25,50 load/rpc_load.js

import http from "k6/http";
import exec from "k6/execution";
import { Rate } from "k6/metrics";

const RPC_URL = __ENV.RPC_URL;
const STEPS = (__ENV.STEPS || "5,10,25").split(",").map(Number);
const WARMUP = __ENV.WARMUP || "5m";
const STEP_DURATION = __ENV.STEP_DURATION || "2m";
const HOLD = __ENV.HOLD || "5m";
const MAX_P95_MS = Number(__ENV.MAX_P95_MS || 2000);
const MAX_ERROR_RATE = Number(__ENV.MAX_ERROR_RATE || 0.05);
const BREAKER_LIMIT = Number(__ENV.BREAKER_LIMIT || 10);

if (!RPC_URL) {
  throw new Error("RPC_URL is required");
}

const RAMP = "10s";

function seconds(duration) {
  const value = parseFloat(duration);
  return duration.endsWith("m") ? value * 60 : value;
}

// Stage plan: warm up at the first step, climb step by step, hold at the top, ramp down.
const stages = [{ target: STEPS[0], duration: RAMP }, { target: STEPS[0], duration: WARMUP }];
STEPS.slice(1).forEach((rate, i) => {
  const isLast = i === STEPS.length - 2;
  stages.push({ target: rate, duration: RAMP }, { target: rate, duration: isLast ? HOLD : STEP_DURATION });
});
stages.push({ target: 0, duration: "30s" });

// Time windows used to tag each request with the step it belongs to.
const windows = [];
let elapsed = 0;
for (let i = 0; i < stages.length; i += 2) {
  const end = elapsed + seconds(stages[i].duration) + seconds(stages[i + 1]?.duration || "0s");
  windows.push({ step: String(stages[i].target), end });
  elapsed = end;
}

function currentStep() {
  const now = exec.instance.currentTestRunDuration / 1000;
  const window = windows.find((w) => now < w.end);
  return window ? window.step : "rampdown";
}

const rpcFailed = new Rate("rpc_failed");

const thresholds = {
  http_req_duration: [{ threshold: `p(95)<${MAX_P95_MS}`, abortOnFail: true, delayAbortEval: "1m" }],
  rpc_failed: [{ threshold: `rate<${MAX_ERROR_RATE}`, abortOnFail: true, delayAbortEval: "1m" }],
};
// Thresholds on tagged submetrics make k6 report every step separately.
for (const rate of STEPS) {
  thresholds[`http_req_duration{step:${rate}}`] = ["max>=0"];
  thresholds[`rpc_failed{step:${rate}}`] = ["rate>=0"];
}

export const options = {
  scenarios: {
    rpc: {
      executor: "ramping-arrival-rate",
      startRate: 0,
      timeUnit: "1s",
      preAllocatedVUs: 2,
      maxVUs: Math.max(50, Math.max(...STEPS) * 4),
      stages,
    },
  },
  thresholds,
  summaryTrendStats: ["med", "p(95)", "p(99)", "max"],
  userAgent: "LoadFault-chainprobe",
};

const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000";

// Weights roughly follow what a dApp frontend sends.
const CALLS = [
  { weight: 30, method: "eth_blockNumber", params: [] },
  { weight: 25, method: "eth_getBlockByNumber", params: ["latest", false] },
  { weight: 20, method: "eth_getBalance", params: [ZERO_ADDRESS, "latest"] },
  { weight: 10, method: "eth_call", params: [{ to: ZERO_ADDRESS, data: "0x" }, "latest"] },
  { weight: 10, method: "eth_getLogs", params: [{ fromBlock: "latest", toBlock: "latest" }] },
  { weight: 5, method: "eth_chainId", params: [] },
];
const TOTAL_WEIGHT = CALLS.reduce((sum, c) => sum + c.weight, 0);

function pickCall() {
  let roll = Math.random() * TOTAL_WEIGHT;
  for (const call of CALLS) {
    roll -= call.weight;
    if (roll < 0) return call;
  }
  return CALLS[0];
}

// Circuit breaker: thresholds are evaluated over the whole run, so a sudden
// collapse late in the test could take a while to trip them. Each VU also
// stops the test after a streak of failed or slow requests.
let streak = 0;

export default function () {
  const call = pickCall();
  const tags = { method: call.method, step: currentStep() };
  const body = JSON.stringify({ jsonrpc: "2.0", id: 1, method: call.method, params: call.params });
  const res = http.post(RPC_URL, body, { headers: { "Content-Type": "application/json" }, tags });

  let failed = res.status !== 200;
  if (!failed) {
    try {
      failed = res.json("error") !== undefined && res.json("error") !== null;
    } catch (e) {
      failed = true;
    }
  }
  rpcFailed.add(failed, tags);

  streak = failed || res.timings.duration > MAX_P95_MS ? streak + 1 : 0;
  if (streak >= BREAKER_LIMIT) {
    exec.test.abort(`circuit breaker: ${streak} failed or slow requests in a row`);
  }
}

export function handleSummary(data) {
  const rows = STEPS.map((rate) => {
    const d = data.metrics[`http_req_duration{step:${rate}}`];
    const f = data.metrics[`rpc_failed{step:${rate}}`];
    const requests = f ? f.values.passes + f.values.fails : 0;
    if (!d || requests === 0) return `${String(rate).padStart(6)} req/s   not reached`;
    const v = d.values;
    const errors = f ? (f.values.rate * 100).toFixed(2) : "0.00";
    return (
      `${String(rate).padStart(6)} req/s` +
      `   p50 ${v.med.toFixed(0).padStart(5)} ms` +
      `   p95 ${v["p(95)"].toFixed(0).padStart(5)} ms` +
      `   p99 ${v["p(99)"].toFixed(0).padStart(5)} ms` +
      `   max ${v.max.toFixed(0).padStart(6)} ms` +
      `   errors ${errors}%` +
      `   requests ${requests}`
    );
  });
  const table = ["", `Load test of ${RPC_URL}`, ...rows, ""].join("\n");
  return {
    stdout: table,
    "load-summary.txt": table,
    "load-summary.json": JSON.stringify(data, null, 2),
  };
}
