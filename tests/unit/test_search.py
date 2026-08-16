import uuid

import pytest

from nevis.application.search import _validate_cursor, fuse_candidates, fuse_mixed_candidates
from nevis.domain.search import (
    MIXED_RANKING_VERSION,
    ClientRetrievalCandidate,
    ClientSearchResult,
    CursorState,
    InvalidSearchCursor,
    InvalidSearchQuery,
    MatchBand,
    ResultType,
    RetrievalCandidate,
    RetrievalMode,
    SearchQuery,
)
from nevis.infrastructure.cursors import SearchCursorCodec
from nevis.settings import Settings


def test_search_query_normalizes_and_fingerprints() -> None:
    query = SearchQuery.create("  pension\n planning ", 10, max_length=100, max_limit=50)

    assert query.text == "pension planning"
    assert (
        query.fingerprint
        == SearchQuery.create("PENSION PLANNING", 10, max_length=100, max_limit=50).fingerprint
    )


@pytest.mark.parametrize(("text", "limit"), [(" ", 10), ("too long", 0), ("ok", 51)])
def test_search_query_rejects_invalid_bounds(text: str, limit: int) -> None:
    with pytest.raises(InvalidSearchQuery, match="invalid search query"):
        SearchQuery.create(text, limit, max_length=4, max_limit=50)


def test_signed_cursor_round_trip_and_context() -> None:
    state = CursorState(
        query_fingerprint="a" * 64,
        tenant_id=uuid.uuid4(),
        embedding_profile_id=uuid.uuid4(),
        mode=RetrievalMode.HYBRID,
        ranking_version=MIXED_RANKING_VERSION,
        match_band=MatchBand.GENERAL,
        fused_score=0.125,
        result_type=ResultType.DOCUMENT,
        result_id=uuid.uuid4(),
        issued_at=1_000,
    )
    codec = SearchCursorCodec("x" * 32, 300, clock=lambda: 1_100)

    assert codec.decode(codec.encode(state)) == state


def test_cursor_rejects_tampering_and_expiry() -> None:
    state = CursorState(
        "a" * 64,
        uuid.uuid4(),
        uuid.uuid4(),
        RetrievalMode.HYBRID,
        MIXED_RANKING_VERSION,
        MatchBand.GENERAL,
        0.1,
        ResultType.DOCUMENT,
        uuid.uuid4(),
        1_000,
    )
    codec = SearchCursorCodec("x" * 32, 30, clock=lambda: 1_100)
    cursor = codec.encode(state)

    with pytest.raises(InvalidSearchCursor):
        codec.decode(cursor)
    with pytest.raises(InvalidSearchCursor):
        SearchCursorCodec("y" * 32, 300, clock=lambda: 1_100).decode(cursor)


def test_production_requires_non_default_cursor_key() -> None:
    with pytest.raises(ValueError, match="cursor signing key"):
        Settings(environment="production")


def _candidate(
    document_id: uuid.UUID, score: float, snippet: str = "Supporting text"
) -> RetrievalCandidate:
    return RetrievalCandidate(
        tenant_id=uuid.UUID(int=1),
        client_id=None,
        source_id=uuid.UUID(int=2),
        document_id=document_id,
        document_version_id=uuid.uuid4(),
        embedding_profile_id=uuid.UUID(int=3),
        indexing_authorization_decision_id=uuid.uuid4(),
        title=f"Document {document_id.int}",
        snippet=snippet,
        score=score,
    )


def test_rrf_fusion_is_deterministic_and_aggregates_documents() -> None:
    first = _candidate(uuid.UUID(int=10), 0.8, "lexical support")
    second = _candidate(uuid.UUID(int=20), 0.9, "semantic support")
    first_semantic = _candidate(first.document_id, 0.99, "incomparable semantic support")

    results = fuse_candidates(
        [first, second],
        [second, first_semantic],
        rrf_constant=60,
        search_decision_id=uuid.UUID(int=4),
    )

    assert [item.provenance.document_id for item in results] == [
        first.document_id,
        second.document_id,
    ]
    assert all(item.scores.lexical is not None for item in results)
    assert all(item.scores.semantic is not None for item in results)
    assert results[0].snippet == "lexical support"


def test_cursor_context_must_match_search() -> None:
    query = SearchQuery.create("pension", 10, max_length=100, max_limit=50)
    state = CursorState(
        query_fingerprint="b" * 64,
        tenant_id=uuid.UUID(int=1),
        embedding_profile_id=uuid.UUID(int=2),
        mode=RetrievalMode.HYBRID,
        ranking_version=MIXED_RANKING_VERSION,
        match_band=MatchBand.GENERAL,
        fused_score=0.1,
        result_type=ResultType.DOCUMENT,
        result_id=uuid.UUID(int=3),
        issued_at=1_000,
    )

    with pytest.raises(InvalidSearchCursor):
        _validate_cursor(
            state,
            query=query,
            tenant_id=state.tenant_id,
            profile_id=state.embedding_profile_id,
            mode=state.mode,
            ranking_version=MIXED_RANKING_VERSION,
        )


def test_mixed_fusion_prefers_exact_identity_and_deduplicates_clients() -> None:
    client_id = uuid.UUID(int=8)
    general = ClientRetrievalCandidate(
        tenant_id=uuid.UUID(int=1),
        client_id=client_id,
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        description="Pensions",
        creation_authorization_decision_id=uuid.UUID(int=9),
        match_band=MatchBand.GENERAL,
        score=0.8,
    )
    exact = ClientRetrievalCandidate(
        tenant_id=general.tenant_id,
        client_id=client_id,
        first_name=general.first_name,
        last_name=general.last_name,
        email=general.email,
        description=general.description,
        creation_authorization_decision_id=general.creation_authorization_decision_id,
        match_band=MatchBand.EXACT_EMAIL,
        score=1.0,
    )
    document = _candidate(uuid.UUID(int=10), 0.99)
    results = fuse_mixed_candidates(
        clients=[exact, general],
        lexical=[document],
        semantic=[],
        rrf_constant=60,
        client_weight=1.0,
        document_lexical_weight=1.0,
        document_semantic_weight=1.0,
        search_decision_id=uuid.UUID(int=4),
        excerpt_length=20,
    )
    assert isinstance(results[0], ClientSearchResult)
    assert results[0].match_band is MatchBand.EXACT_EMAIL
    assert sum(isinstance(item, ClientSearchResult) for item in results) == 1


def test_general_mixed_fusion_uses_weights_and_stable_type_tie_breaker() -> None:
    client = ClientRetrievalCandidate(
        tenant_id=uuid.UUID(int=1),
        client_id=uuid.UUID(int=8),
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        description="Retirement",
        creation_authorization_decision_id=uuid.UUID(int=9),
        match_band=MatchBand.GENERAL,
        score=0.5,
    )
    document = _candidate(uuid.UUID(int=10), 0.99)
    weighted = fuse_mixed_candidates(
        clients=[client],
        lexical=[document],
        semantic=[],
        rrf_constant=60,
        client_weight=2.0,
        document_lexical_weight=1.0,
        document_semantic_weight=1.0,
        search_decision_id=uuid.UUID(int=4),
        excerpt_length=20,
    )
    assert isinstance(weighted[0], ClientSearchResult)
    assert weighted[0].fused_score == pytest.approx(2 / 61)

    tied = fuse_mixed_candidates(
        clients=[client],
        lexical=[document],
        semantic=[],
        rrf_constant=60,
        client_weight=1.0,
        document_lexical_weight=1.0,
        document_semantic_weight=1.0,
        search_decision_id=uuid.UUID(int=4),
        excerpt_length=20,
    )
    assert [item.type for item in tied] == [ResultType.CLIENT, ResultType.DOCUMENT]


def test_general_client_rank_is_independent_of_exact_precedence_bands() -> None:
    exact = ClientRetrievalCandidate(
        tenant_id=uuid.UUID(int=1),
        client_id=uuid.UUID(int=7),
        first_name="Exact",
        last_name="Client",
        email="exact@example.com",
        description=None,
        creation_authorization_decision_id=uuid.UUID(int=9),
        match_band=MatchBand.EXACT_NAME,
        score=1.0,
    )
    general = ClientRetrievalCandidate(
        tenant_id=exact.tenant_id,
        client_id=uuid.UUID(int=8),
        first_name="General",
        last_name="Client",
        email="general@example.com",
        description="Client evidence",
        creation_authorization_decision_id=exact.creation_authorization_decision_id,
        match_band=MatchBand.GENERAL,
        score=0.5,
    )
    results = fuse_mixed_candidates(
        clients=[exact, general],
        lexical=[],
        semantic=[],
        rrf_constant=60,
        client_weight=1.0,
        document_lexical_weight=1.0,
        document_semantic_weight=1.0,
        search_decision_id=uuid.UUID(int=4),
        excerpt_length=20,
    )
    assert [item.match_band for item in results] == [MatchBand.EXACT_NAME, MatchBand.GENERAL]
    assert results[1].ranks.client_lexical == 1
    assert results[1].fused_score == pytest.approx(1 / 61)
