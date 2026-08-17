"""Evaluate the versioned, seeded mixed-search policy through its HTTP boundary."""

import json
import math
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

fixture = json.loads(Path("tests/fixtures/mixed_search_relevance.json").read_text())
bakeoff = json.loads(Path("tests/fixtures/reranker_bakeoff.json").read_text())
base_url = os.getenv("NEVIS_EVALUATION_URL", "http://127.0.0.1:8001").rstrip("/")
tenant = os.getenv("NEVIS_EVALUATION_TENANT", "nevis-global")
advisor = os.getenv("NEVIS_EVALUATION_ADVISOR", "local-advisor")
recall_k = int(fixture["recall_k"])
precision_k = int(fixture["precision_k"])
ndcg_k = int(fixture["ndcg_k"])
result_limit = max(recall_k, precision_k, ndcg_k)


def discounted_gain(relevance: list[int]) -> float:
    return sum((2**gain - 1) / math.log2(rank + 1) for rank, gain in enumerate(relevance, 1))


metrics: list[tuple[float, float, float, float]] = []
latencies: list[float] = []
case_results: list[dict[str, object]] = []
result_type_mix = {"client": 0, "document": 0}
zero_result_count = 0
for case in fixture["cases"]:
    query = urllib.parse.urlencode({"q": case["query"], "limit": result_limit})
    request = urllib.request.Request(
        f"{base_url}/search?{query}",
        headers={"X-Nevis-Tenant": tenant, "X-Nevis-Advisor": advisor},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=10) as response:
        page = json.load(response)
    latency_ms = (time.perf_counter() - started) * 1_000
    latencies.append(latency_ms)
    assert page["ranking_version"] == fixture["ranking_version"]
    assert page["mode"] == case["expected_mode"]

    returned = [(item["type"], item["title"]) for item in page["results"]]
    for result_type, _ in returned:
        result_type_mix[result_type] += 1
    zero_result_count += not returned
    judgments = {
        (item["type"], item["title"]): int(item["relevance"]) for item in case["judgments"]
    }
    positives = {identity for identity, relevance in judgments.items() if relevance > 0}
    if case.get("expect_empty"):
        assert returned == [], f"expected an empty result for {case['label']}"
        recall = precision = reciprocal_rank = ndcg = 1.0
    else:
        recall = len(positives.intersection(returned[:recall_k])) / len(positives)
        precision = sum(identity in positives for identity in returned[:precision_k]) / max(
            min(len(returned), precision_k), 1
        )
        positive_ranks = [
            returned.index(identity) + 1 for identity in positives if identity in returned
        ]
        reciprocal_rank = 1.0 / min(positive_ranks) if positive_ranks else 0.0
        gains = [judgments.get(identity, 0) for identity in returned[:ndcg_k]]
        ideal = discounted_gain(sorted(judgments.values(), reverse=True)[:ndcg_k])
        ndcg = discounted_gain(gains) / ideal if ideal else 1.0
        assert recall == 1.0, f"candidate/final recall failed: {case['label']}"
        if required := case.get("required_first"):
            assert returned[0] == (required["type"], required["title"]), case["label"]
    metrics.append((recall, precision, reciprocal_rank, ndcg))
    case_results.append(
        {
            "label": case["label"],
            "split": case["split"],
            f"recall_at_{recall_k}": round(recall, 4),
            f"precision_at_{precision_k}": round(precision, 4),
            "reciprocal_rank": round(reciprocal_rank, 4),
            f"ndcg_at_{ndcg_k}": round(ndcg, 4),
            "latency_ms": round(latency_ms, 2),
        }
    )

latencies.sort()
p95_index = max(math.ceil(len(latencies) * 0.95) - 1, 0)
print(
    json.dumps(
        {
            "ranking_version": fixture["ranking_version"],
            "cases": case_results,
            "candidate_recall_at_10": bakeoff["candidate_recall_at_10"],
            f"recall_at_{recall_k}": round(sum(value[0] for value in metrics) / len(metrics), 4),
            f"precision_at_{precision_k}": round(
                sum(value[1] for value in metrics) / len(metrics), 4
            ),
            "mrr": round(sum(value[2] for value in metrics) / len(metrics), 4),
            f"ndcg_at_{ndcg_k}": round(sum(value[3] for value in metrics) / len(metrics), 4),
            "p95_ms": round(latencies[p95_index], 2),
            "result_type_mix": result_type_mix,
            "zero_result_rate": round(zero_result_count / len(fixture["cases"]), 4),
        },
        sort_keys=True,
    )
)
