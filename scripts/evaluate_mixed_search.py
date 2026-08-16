"""Evaluate labelled mixed-search relevance against the Compose smoke API."""

import json
import urllib.parse
import urllib.request
from pathlib import Path

fixture = json.loads(Path("tests/fixtures/mixed_search_relevance.json").read_text())
k = int(fixture["k"])
recalls: list[float] = []
reciprocal_ranks: list[float] = []
case_results: list[dict[str, object]] = []

for case in fixture["cases"]:
    query = urllib.parse.urlencode({"q": case["query"], "limit": k})
    request = urllib.request.Request(
        f"http://127.0.0.1:8000/search?{query}",
        headers={
            "X-Nevis-Tenant": "nevis-global",
            "X-Nevis-Advisor": "compose-smoke-advisor",
        },
    )
    with urllib.request.urlopen(request) as response:
        page = json.load(response)
    assert page["ranking_version"] == fixture["ranking_version"]
    returned = [(item["type"], item["title"]) for item in page["results"]]
    relevant = [(item["type"], item["title"]) for item in case["relevant"]]
    if case.get("expect_empty"):
        assert returned == []
        recall = 1.0
        reciprocal_rank = 1.0
    else:
        hits = [identity for identity in relevant if identity in returned]
        recall = len(hits) / len(relevant)
        ranks = [returned.index(identity) + 1 for identity in relevant if identity in returned]
        reciprocal_rank = 1.0 / min(ranks) if ranks else 0.0
        assert recall == 1.0, f"failed relevance case: {case['label']}"
    recalls.append(recall)
    reciprocal_ranks.append(reciprocal_rank)
    case_results.append(
        {
            "label": case["label"],
            "recall_at_k": round(recall, 4),
            "reciprocal_rank": round(reciprocal_rank, 4),
        }
    )

summary = {
    "ranking_version": fixture["ranking_version"],
    "cases": case_results,
    "recall_at_k": round(sum(recalls) / len(recalls), 4),
    "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4),
}
print(json.dumps(summary, sort_keys=True))
