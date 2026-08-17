import json
import uuid
from pathlib import Path

from nevis.application.search import fuse_candidates
from nevis.domain.search import RetrievalCandidate


def _candidate(document_id: int, score: float, title: str) -> RetrievalCandidate:
    return RetrievalCandidate(
        tenant_id=uuid.UUID(int=1),
        client_id=uuid.UUID(int=5),
        client_name="Ada Lovelace",
        source_id=uuid.UUID(int=2),
        document_id=uuid.UUID(int=document_id),
        document_version_id=uuid.UUID(int=document_id + 100),
        embedding_profile_id=uuid.UUID(int=3),
        indexing_authorization_decision_id=uuid.UUID(int=4),
        title=title,
        snippet=f"{title} evidence",
        score=score,
    )


def test_labelled_relevance_fixture_covers_required_search_cases() -> None:
    fixtures = json.loads(Path("tests/fixtures/search_relevance.json").read_text())

    assert {item["evidence"] for item in fixtures} == {
        "lexical",
        "semantic",
        "hybrid",
        "threshold",
        "aggregation",
        "version",
    }


def test_mixed_relevance_fixture_is_versioned_and_covers_result_branches() -> None:
    fixture = json.loads(Path("tests/fixtures/mixed_search_relevance.json").read_text())

    assert fixture["ranking_version"] == "mixed-rrf-v5"
    labels = {item["label"] for item in fixture["cases"]}
    assert "one-character-short semantic term" in labels
    assert "misspelled client name" in labels
    assert "misspelled document title" in labels
    assert "short-name collision stays empty" in labels
    assert "misspelled content term" in labels
    assert "near-miss complete identifier" in labels
    assert fixture["recall_k"] == 5
    assert fixture["precision_k"] == 5
    assert fixture["ndcg_k"] == 10
    assert {item["split"] for item in fixture["cases"]} == {"selection", "regression"}
    assert {item["expected_mode"] for item in fixture["cases"]} == {
        "hybrid",
        "lexical_identifier",
    }
    relevant_types = {
        judgment["type"] for case in fixture["cases"] for judgment in case["judgments"]
    }
    assert relevant_types == {"client", "document"}


def test_reranker_bakeoff_records_candidate_recall_quality_and_latency() -> None:
    fixture = json.loads(Path("tests/fixtures/reranker_bakeoff.json").read_text())

    assert fixture["candidate_recall_at_10"] == 1.0
    selected = fixture["models"][fixture["selected_model"]]
    assert selected["address_positive_score"] > selected["address_hard_negative_score"]
    assert selected["p95_ms_at_9_candidates"] < fixture["latency_budget_ms"]
    assert fixture["models"]["bge_base"]["p95_ms_at_18_candidates"] > fixture["latency_budget_ms"]


def test_hybrid_fusion_rewards_complementary_evidence_and_aggregates_chunks() -> None:
    hybrid = _candidate(10, 0.7, "Hybrid evidence")
    lexical_only = _candidate(20, 0.9, "Lexical evidence")
    repeated_hybrid_chunk = _candidate(10, 0.6, "Hybrid evidence")

    results = fuse_candidates(
        [lexical_only, hybrid, repeated_hybrid_chunk],
        [hybrid],
        rrf_constant=60,
        search_decision_id=uuid.UUID(int=5),
    )

    assert results[0].provenance.document_id == hybrid.document_id
    assert len([item for item in results if item.provenance.document_id == hybrid.document_id]) == 1
    assert results[0].scores.lexical == 0.7
    assert results[0].scores.semantic == 0.7


def test_fusion_tie_breaks_by_stable_document_identity() -> None:
    later = _candidate(20, 0.8, "Later")
    earlier = _candidate(10, 0.8, "Earlier")

    results = fuse_candidates(
        [later, earlier],
        [earlier, later],
        rrf_constant=60,
        search_decision_id=uuid.UUID(int=5),
    )

    assert [item.provenance.document_id.int for item in results] == [10, 20]
