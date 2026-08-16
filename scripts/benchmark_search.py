"""Repeatable warm-search p95 check against the local API."""

import json
import os
import statistics
import time
import urllib.parse
import urllib.request

iterations = int(os.getenv("NEVIS_SEARCH_BENCHMARK_ITERATIONS", "30"))
target_ms = float(os.getenv("NEVIS_SEARCH_P95_TARGET_MS", "800"))
base_url = os.getenv("NEVIS_SEARCH_BENCHMARK_URL", "http://127.0.0.1:8000")
query = urllib.parse.urlencode({"q": "Nevis indexing", "limit": 20})
request = urllib.request.Request(
    f"{base_url}/search?{query}",
    headers={
        "X-Nevis-Tenant": "nevis-global",
        "X-Nevis-Advisor": "compose-smoke-advisor",
    },
)

# Warm provider, connection pools, and PostgreSQL buffers before measurement.
with urllib.request.urlopen(request) as response:
    assert response.status == 200

samples: list[float] = []
for _ in range(iterations):
    started = time.perf_counter()
    with urllib.request.urlopen(request) as response:
        body = json.load(response)
        assert response.status == 200 and body["mode"] in {"hybrid", "lexical_degraded"}
    samples.append((time.perf_counter() - started) * 1_000)

p95 = statistics.quantiles(samples, n=100, method="inclusive")[94]
summary = {
    "iterations": iterations,
    "p50_ms": round(statistics.median(samples), 2),
    "p95_ms": round(p95, 2),
    "target_ms": target_ms,
}
print(json.dumps(summary, sort_keys=True))
if p95 > target_ms:
    raise SystemExit(f"search p95 {p95:.2f}ms exceeds target {target_ms:.2f}ms")
