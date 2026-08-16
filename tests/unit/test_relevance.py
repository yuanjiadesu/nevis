import json
import uuid
from pathlib import Path

from nevis.application.search import fuse_candidates
from nevis.domain.search import RetrievalCandidate


def _candidate(document_id: int, score: float, title: str) -> RetrievalCandidate:
    return RetrievalCandidate(
        tenant_id=uuid.UUID(int=1),
        client_id=None,
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

    assert fixture["ranking_version"] == "mixed-rrf-v1"
    assert fixture["k"] == 5
    assert {item["evidence"] for item in fixture["cases"]} == {
        "exact_email",
        "exact_name",
        "client_description",
        "document_semantic",
        "ambiguous_mixed",
        "threshold",
    }
    relevant_types = {
        relevant["type"] for case in fixture["cases"] for relevant in case["relevant"]
    }
    assert relevant_types == {"client", "document"}


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
