import time
import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from nevis.domain.authorization import AuthorizationAction, AuthorizationContext
from nevis.domain.embeddings import EmbeddingProvider
from nevis.domain.search import (
    MIXED_RANKING_VERSION,
    BranchRanks,
    ClientRetrievalCandidate,
    ClientSearchProvenance,
    ClientSearchResult,
    ComponentScores,
    CursorState,
    DocumentSearchProvenance,
    InvalidSearchCursor,
    MatchBand,
    MixedSearchResult,
    ResultType,
    RetrievalCandidate,
    RetrievalMode,
    SearchDependencyUnavailable,
    SearchPage,
    SearchQuery,
    SearchResult,
)
from nevis.infrastructure.cursors import SearchCursorCodec
from nevis.infrastructure.embeddings import EmbeddingProviderUnavailable
from nevis.infrastructure.models import EmbeddingProfile
from nevis.infrastructure.repositories import (
    append_audit_event,
    get_active_embedding_profile,
    search_exact_email_clients,
    search_exact_name_clients,
    search_lexical_candidates,
    search_lexical_clients,
    search_semantic_candidates,
)
from nevis.infrastructure.telemetry import search_telemetry_fields

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class _DocumentFusion:
    candidate: RetrievalCandidate
    fused: float = 0.0
    lexical_score: float | None = None
    semantic_score: float | None = None
    lexical_rank: int | None = None
    semantic_rank: int | None = None


def _result_identity(result: MixedSearchResult) -> uuid.UUID:
    return (
        result.provenance.client_id
        if isinstance(result, ClientSearchResult)
        else result.provenance.document_id
    )


def mixed_order_key(result: MixedSearchResult) -> tuple[int, float, str, int]:
    return (
        int(result.match_band),
        -result.fused_score,
        result.type.value,
        _result_identity(result).int,
    )


def fuse_mixed_candidates(
    *,
    clients: list[ClientRetrievalCandidate],
    lexical: list[RetrievalCandidate],
    semantic: list[RetrievalCandidate],
    rrf_constant: int,
    client_weight: float,
    document_lexical_weight: float,
    document_semantic_weight: float,
    search_decision_id: uuid.UUID,
    excerpt_length: int,
) -> list[MixedSearchResult]:
    documents: dict[uuid.UUID, _DocumentFusion] = {}
    for branch, candidates, weight in (
        ("lexical", lexical, document_lexical_weight),
        ("semantic", semantic, document_semantic_weight),
    ):
        seen: set[uuid.UUID] = set()
        for rank, candidate in enumerate(candidates, start=1):
            entry = documents.setdefault(candidate.document_id, _DocumentFusion(candidate))
            if candidate.document_id not in seen:
                entry.fused += weight / (rrf_constant + rank)
                seen.add(candidate.document_id)
            current = getattr(entry, f"{branch}_score")
            if current is None or candidate.score > current:
                setattr(entry, f"{branch}_score", candidate.score)
                setattr(entry, f"{branch}_rank", rank)

    results: list[MixedSearchResult] = []
    for entry in documents.values():
        candidate = entry.candidate
        results.append(
            SearchResult(
                type=ResultType.DOCUMENT,
                title=candidate.title,
                snippet=candidate.snippet,
                fused_score=entry.fused,
                match_band=MatchBand.GENERAL,
                scores=ComponentScores(entry.lexical_score, entry.semantic_score),
                ranks=BranchRanks(
                    document_lexical=entry.lexical_rank,
                    document_semantic=entry.semantic_rank,
                ),
                provenance=DocumentSearchProvenance(
                    tenant_id=candidate.tenant_id,
                    client_id=candidate.client_id,
                    source_id=candidate.source_id,
                    document_id=candidate.document_id,
                    document_version_id=candidate.document_version_id,
                    embedding_profile_id=candidate.embedding_profile_id,
                    indexing_authorization_decision_id=(
                        candidate.indexing_authorization_decision_id
                    ),
                    search_authorization_decision_id=search_decision_id,
                ),
            )
        )

    unique_clients: dict[uuid.UUID, tuple[ClientRetrievalCandidate, int]] = {}
    band_positions: dict[MatchBand, int] = {}
    for client_candidate in clients:
        rank = band_positions.get(client_candidate.match_band, 0) + 1
        band_positions[client_candidate.match_band] = rank
        previous = unique_clients.get(client_candidate.client_id)
        if previous is None or client_candidate.match_band < previous[0].match_band:
            unique_clients[client_candidate.client_id] = (client_candidate, rank)
    for client_candidate, rank in unique_clients.values():
        results.append(
            ClientSearchResult(
                type=ResultType.CLIENT,
                title=f"{client_candidate.first_name} {client_candidate.last_name}",
                email=client_candidate.email,
                excerpt=(client_candidate.description or "")[:excerpt_length] or None,
                fused_score=client_weight / (rrf_constant + rank),
                match_band=client_candidate.match_band,
                ranks=BranchRanks(client_lexical=rank),
                provenance=ClientSearchProvenance(
                    tenant_id=client_candidate.tenant_id,
                    client_id=client_candidate.client_id,
                    creation_authorization_decision_id=(
                        client_candidate.creation_authorization_decision_id
                    ),
                    search_authorization_decision_id=search_decision_id,
                ),
            )
        )
    return sorted(results, key=mixed_order_key)


def fuse_candidates(
    lexical: list[RetrievalCandidate],
    semantic: list[RetrievalCandidate],
    *,
    rrf_constant: int,
    search_decision_id: uuid.UUID,
) -> list[SearchResult]:
    """Compatibility facade for document-only ranking tests."""
    return [
        item
        for item in fuse_mixed_candidates(
            clients=[],
            lexical=lexical,
            semantic=semantic,
            rrf_constant=rrf_constant,
            client_weight=1.0,
            document_lexical_weight=1.0,
            document_semantic_weight=1.0,
            search_decision_id=search_decision_id,
            excerpt_length=180,
        )
        if isinstance(item, SearchResult)
    ]


def _validate_cursor(
    cursor: CursorState,
    *,
    query: SearchQuery,
    tenant_id: uuid.UUID,
    profile_id: uuid.UUID,
    mode: RetrievalMode,
    ranking_version: str,
) -> None:
    if (
        cursor.query_fingerprint != query.fingerprint
        or cursor.tenant_id != tenant_id
        or cursor.embedding_profile_id != profile_id
        or cursor.mode != mode
        or cursor.ranking_version != ranking_version
    ):
        raise InvalidSearchCursor("invalid search cursor")


async def search_documents(
    session: AsyncSession,
    *,
    query: SearchQuery,
    request_id: str,
    cursor: str | None,
    authorization: AuthorizationContext,
    provider: EmbeddingProvider,
    cursor_codec: SearchCursorCodec,
    lexical_limit: int,
    semantic_limit: int,
    client_limit: int,
    semantic_threshold: float,
    rrf_constant: int,
    snippet_length: int,
    client_excerpt_length: int,
    client_weight: float,
    document_lexical_weight: float,
    document_semantic_weight: float,
    ranking_version: str = MIXED_RANKING_VERSION,
) -> SearchPage:
    started = time.perf_counter()
    decision = authorization.decision
    if (
        decision.decision_id is None
        or decision.result != "allow"
        or decision.action is not AuthorizationAction.MIXED_SEARCH
    ):
        raise SearchDependencyUnavailable("search authorization unavailable")
    async with session.begin():
        profile: EmbeddingProfile | None = await get_active_embedding_profile(session)
        if profile is None:
            raise SearchDependencyUnavailable("search profile unavailable")
        mode = RetrievalMode.HYBRID
        try:
            embedding: list[float] | None = await provider.embed_query(query.text)
        except EmbeddingProviderUnavailable:
            embedding = None
            mode = RetrievalMode.LEXICAL_DEGRADED
        cursor_state = cursor_codec.decode(cursor) if cursor else None
        if cursor_state is not None:
            _validate_cursor(
                cursor_state,
                query=query,
                tenant_id=authorization.tenant_id,
                profile_id=profile.id,
                mode=mode,
                ranking_version=ranking_version,
            )
        exact_email = await search_exact_email_clients(
            session, tenant_id=authorization.tenant_id, query=query.text
        )
        exact_name = await search_exact_name_clients(
            session, tenant_id=authorization.tenant_id, query=query.text, limit=client_limit
        )
        client_lexical = await search_lexical_clients(
            session, tenant_id=authorization.tenant_id, query=query.text, limit=client_limit
        )
        lexical = await search_lexical_candidates(
            session,
            tenant_id=authorization.tenant_id,
            profile_id=profile.id,
            query=query.text,
            limit=lexical_limit,
            snippet_length=snippet_length,
        )
        semantic = (
            await search_semantic_candidates(
                session,
                tenant_id=authorization.tenant_id,
                profile_id=profile.id,
                embedding=embedding,
                threshold=semantic_threshold,
                limit=semantic_limit,
                snippet_length=snippet_length,
            )
            if embedding is not None
            else []
        )
        ranked = fuse_mixed_candidates(
            clients=[*exact_email, *exact_name, *client_lexical],
            lexical=lexical,
            semantic=semantic,
            rrf_constant=rrf_constant,
            client_weight=client_weight,
            document_lexical_weight=document_lexical_weight,
            document_semantic_weight=document_semantic_weight,
            search_decision_id=decision.decision_id,
            excerpt_length=client_excerpt_length,
        )
        if cursor_state is not None:
            boundary = (
                int(cursor_state.match_band),
                -cursor_state.fused_score,
                cursor_state.result_type.value,
                cursor_state.result_id.int,
            )
            ranked = [item for item in ranked if mixed_order_key(item) > boundary]
        page_results = ranked[: query.limit]
        next_cursor = None
        if len(ranked) > query.limit:
            last = page_results[-1]
            next_cursor = cursor_codec.encode(
                CursorState(
                    query_fingerprint=query.fingerprint,
                    tenant_id=authorization.tenant_id,
                    embedding_profile_id=profile.id,
                    mode=mode,
                    ranking_version=ranking_version,
                    match_band=last.match_band,
                    fused_score=last.fused_score,
                    result_type=last.type,
                    result_id=_result_identity(last),
                    issued_at=int(time.time()),
                )
            )
        duration_ms = (time.perf_counter() - started) * 1_000
        degradation_code = (
            "embedding_unavailable" if mode is RetrievalMode.LEXICAL_DEGRADED else None
        )
        all_clients = [*exact_email, *exact_name, *client_lexical]
        typed_ids = [f"{item.type.value}:{_result_identity(item)}" for item in page_results]
        rank_evidence = [
            {
                "type": item.type.value,
                "match_band": int(item.match_band),
                "client_lexical": item.ranks.client_lexical,
                "document_lexical": item.ranks.document_lexical,
                "document_semantic": item.ranks.document_semantic,
            }
            for item in page_results
        ]
        await append_audit_event(
            session,
            event_type="mixed.search.completed",
            request_id=request_id,
            decision=decision,
            metadata={
                "query_fingerprint": query.fingerprint,
                "ranking_version": ranking_version,
                "mode": mode.value,
                "result_count": len(page_results),
                "result_ids": typed_ids,
                "client_result_count": sum(item.type is ResultType.CLIENT for item in page_results),
                "document_result_count": sum(
                    item.type is ResultType.DOCUMENT for item in page_results
                ),
                "client_candidate_count": len({item.client_id for item in all_clients}),
                "document_candidate_count": len(
                    {item.document_id for item in [*lexical, *semantic]}
                ),
                "scores": [round(item.fused_score, 6) for item in page_results],
                "rank_evidence": rank_evidence,
                "embedding_profile_id": str(profile.id),
                "duration_ms": round(duration_ms, 2),
                "degradation_code": degradation_code,
            },
        )
        logger.info(
            "mixed_search_completed",
            **search_telemetry_fields(
                mode=mode.value,
                outcome="success",
                duration_ms=duration_ms,
                lexical_candidates=len(lexical),
                semantic_candidates=len(semantic),
                client_candidates=len({item.client_id for item in all_clients}),
                result_count=len(page_results),
                degradation_code=degradation_code,
            ),
        )
    return SearchPage(
        ranking_version=ranking_version,
        mode=mode,
        results=tuple(page_results),
        next_cursor=next_cursor,
    )
