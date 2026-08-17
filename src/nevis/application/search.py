import time
import uuid
from dataclasses import dataclass, replace

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from nevis.application.spelling import correct_final_token
from nevis.domain.authorization import AuthorizationAction, AuthorizationContext
from nevis.domain.embeddings import EmbeddingProvider
from nevis.domain.reranking import RerankerProvider
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
    RerankedCandidate,
    ResultType,
    RetrievalCandidate,
    RetrievalMode,
    SearchDependencyUnavailable,
    SearchPage,
    SearchQuery,
    SearchResult,
    is_identifier_query,
)
from nevis.infrastructure.cursors import SearchCursorCodec
from nevis.infrastructure.embeddings import EmbeddingProviderUnavailable
from nevis.infrastructure.models import EmbeddingProfile
from nevis.infrastructure.repositories import (
    append_audit_event,
    get_active_embedding_profile,
    search_exact_email_clients,
    search_exact_name_clients,
    search_fuzzy_name_clients,
    search_fuzzy_title_candidates,
    search_lexical_candidates,
    search_lexical_clients,
    search_semantic_candidates,
)
from nevis.infrastructure.reranking import RerankerProviderUnavailable
from nevis.infrastructure.telemetry import search_telemetry_fields

logger = structlog.get_logger(__name__)

TRIGRAM_SIMILARITY_THRESHOLD = 0.5


@dataclass(slots=True)
class _DocumentFusion:
    candidate: RetrievalCandidate
    fused: float = 0.0
    lexical_score: float | None = None
    semantic_score: float | None = None
    lexical_rank: int | None = None
    semantic_rank: int | None = None
    reranker_score: float | None = None
    reranker_rank: int | None = None


def select_reranker_candidates(
    lexical: list[RetrievalCandidate],
    semantic: list[RetrievalCandidate],
    *,
    rrf_constant: int,
    lexical_weight: float,
    semantic_weight: float,
    limit: int,
) -> list[RetrievalCandidate]:
    """Fuse chunk branches for recall before the expensive evidence pass."""
    scores: dict[uuid.UUID, float] = {}
    candidates: dict[uuid.UUID, RetrievalCandidate] = {}
    for branch, weight in ((lexical, lexical_weight), (semantic, semantic_weight)):
        for rank, candidate in enumerate(branch, start=1):
            candidates.setdefault(candidate.chunk_id, candidate)
            scores[candidate.chunk_id] = scores.get(candidate.chunk_id, 0.0) + weight / (
                rrf_constant + rank
            )
    ordered = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id.int))
    return [candidates[chunk_id] for chunk_id in ordered[:limit]]


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


def _result_key(result: MixedSearchResult) -> tuple[ResultType, uuid.UUID]:
    return result.type, _result_identity(result)


def _fuzzy_document_results(
    candidates: list[RetrievalCandidate],
    *,
    search_decision_id: uuid.UUID,
) -> list[MixedSearchResult]:
    return [
        SearchResult(
            type=ResultType.DOCUMENT,
            title=candidate.title,
            client_name=candidate.client_name,
            snippet=candidate.snippet,
            fused_score=0.0,
            match_band=MatchBand.FUZZY,
            scores=ComponentScores(None, None, None),
            ranks=BranchRanks(),
            provenance=DocumentSearchProvenance(
                tenant_id=candidate.tenant_id,
                client_id=candidate.client_id,
                source_id=candidate.source_id,
                document_id=candidate.document_id,
                document_version_id=candidate.document_version_id,
                embedding_profile_id=candidate.embedding_profile_id,
                indexing_authorization_decision_id=(candidate.indexing_authorization_decision_id),
                search_authorization_decision_id=search_decision_id,
            ),
        )
        for candidate in candidates
    ]


def merge_approximate_branches(
    ordinary: list[MixedSearchResult],
    branches: list[list[MixedSearchResult]],
    *,
    rrf_constant: int,
) -> list[MixedSearchResult]:
    """Merge fallback branch positions without comparing their raw scores."""
    ordinary_keys = {_result_key(item) for item in ordinary}
    scores: dict[tuple[ResultType, uuid.UUID], float] = {}
    selected: dict[tuple[ResultType, uuid.UUID], MixedSearchResult] = {}
    for branch in branches:
        seen: set[tuple[ResultType, uuid.UUID]] = set()
        for rank, result in enumerate(branch, start=1):
            key = _result_key(result)
            if key in ordinary_keys or key in seen:
                continue
            seen.add(key)
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_constant + rank)
            selected.setdefault(key, result)
    approximate = [
        replace(result, fused_score=scores[key], match_band=MatchBand.FUZZY)
        for key, result in selected.items()
    ]
    return sorted([*ordinary, *approximate], key=mixed_order_key)


def fuse_mixed_candidates(
    *,
    clients: list[ClientRetrievalCandidate],
    lexical: list[RetrievalCandidate],
    semantic: list[RetrievalCandidate],
    rrf_constant: int,
    client_weight: float,
    document_lexical_weight: float,
    document_semantic_weight: float,
    reranked: list[RerankedCandidate] | None = None,
    document_reranker_weight: float = 1.0,
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

    if reranked is not None:
        allowed_documents = {item.candidate.document_id for item in reranked}
        allowed_documents.update(
            candidate.document_id for candidate in lexical if candidate.title_match
        )
        documents = {
            document_id: entry
            for document_id, entry in documents.items()
            if document_id in allowed_documents
        }
        seen_documents: set[uuid.UUID] = set()
        for rank, item in enumerate(reranked, start=1):
            document_id = item.candidate.document_id
            reranked_entry = documents.get(document_id)
            if reranked_entry is None or document_id in seen_documents:
                continue
            seen_documents.add(document_id)
            reranked_entry.candidate = item.candidate
            reranked_entry.reranker_score = item.score
            reranked_entry.reranker_rank = rank
            reranked_entry.fused += document_reranker_weight / (rrf_constant + rank)

    results: list[MixedSearchResult] = []
    for entry in documents.values():
        candidate = entry.candidate
        results.append(
            SearchResult(
                type=ResultType.DOCUMENT,
                title=candidate.title,
                client_name=candidate.client_name,
                snippet=candidate.snippet,
                fused_score=entry.fused,
                match_band=MatchBand.GENERAL,
                scores=ComponentScores(
                    entry.lexical_score, entry.semantic_score, entry.reranker_score
                ),
                ranks=BranchRanks(
                    document_lexical=entry.lexical_rank,
                    document_semantic=entry.semantic_rank,
                    document_reranker=entry.reranker_rank,
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
        is_fuzzy = client_candidate.match_band is MatchBand.FUZZY
        results.append(
            ClientSearchResult(
                type=ResultType.CLIENT,
                title=f"{client_candidate.first_name} {client_candidate.last_name}",
                email=client_candidate.email,
                excerpt=(client_candidate.description or "")[:excerpt_length] or None,
                fused_score=(1.0 if is_fuzzy else client_weight) / (rrf_constant + rank),
                match_band=client_candidate.match_band,
                ranks=BranchRanks() if is_fuzzy else BranchRanks(client_lexical=rank),
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
    reranker: RerankerProvider,
    cursor_codec: SearchCursorCodec,
    lexical_limit: int,
    semantic_limit: int,
    client_limit: int,
    semantic_candidate_threshold: float,
    reranker_limit: int,
    reranker_threshold: float,
    rrf_constant: int,
    snippet_length: int,
    client_excerpt_length: int,
    client_weight: float,
    document_lexical_weight: float,
    document_semantic_weight: float,
    document_reranker_weight: float,
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
        identifier_query = is_identifier_query(query.text)
        mode = RetrievalMode.LEXICAL_IDENTIFIER if identifier_query else RetrievalMode.HYBRID
        embedding: list[float] | None = None
        if not identifier_query:
            try:
                embedding = await provider.embed_query(query.text)
            except EmbeddingProviderUnavailable:
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
                threshold=semantic_candidate_threshold,
                limit=semantic_limit,
                snippet_length=snippet_length,
            )
            if embedding is not None
            else []
        )
        reranker_candidates: list[RetrievalCandidate] = []
        reranked: list[RerankedCandidate] | None = None
        reranker_duration_ms: float | None = None
        if mode is RetrievalMode.HYBRID:
            reranker_candidates = select_reranker_candidates(
                lexical,
                semantic,
                rrf_constant=rrf_constant,
                lexical_weight=document_lexical_weight,
                semantic_weight=document_semantic_weight,
                limit=reranker_limit,
            )
            if reranker_candidates:
                reranker_started = time.perf_counter()
                try:
                    reranker_scores = await reranker.rerank(
                        query.text, [candidate.content for candidate in reranker_candidates]
                    )
                except RerankerProviderUnavailable:
                    mode = RetrievalMode.HYBRID_UNRERANKED
                else:
                    reranked = sorted(
                        (
                            RerankedCandidate(candidate, score)
                            for candidate, score in zip(
                                reranker_candidates, reranker_scores, strict=True
                            )
                            if score >= reranker_threshold
                        ),
                        key=lambda item: (-item.score, item.candidate.chunk_id.int),
                    )
                reranker_duration_ms = (time.perf_counter() - reranker_started) * 1_000
        ordinary_ranked = fuse_mixed_candidates(
            clients=[*exact_email, *exact_name, *client_lexical],
            lexical=lexical,
            semantic=semantic,
            rrf_constant=rrf_constant,
            client_weight=client_weight,
            document_lexical_weight=document_lexical_weight,
            document_semantic_weight=document_semantic_weight,
            reranked=reranked,
            document_reranker_weight=document_reranker_weight,
            search_decision_id=decision.decision_id,
            excerpt_length=client_excerpt_length,
        )

        fuzzy_clients: list[ClientRetrievalCandidate] = []
        fuzzy_titles: list[RetrievalCandidate] = []
        if not identifier_query:
            if not exact_email and not exact_name and not client_lexical:
                fuzzy_clients = await search_fuzzy_name_clients(
                    session,
                    tenant_id=authorization.tenant_id,
                    query=query.text,
                    threshold=TRIGRAM_SIMILARITY_THRESHOLD,
                    limit=client_limit,
                )
            if not lexical:
                fuzzy_titles = await search_fuzzy_title_candidates(
                    session,
                    tenant_id=authorization.tenant_id,
                    profile_id=profile.id,
                    query=query.text,
                    threshold=TRIGRAM_SIMILARITY_THRESHOLD,
                    limit=lexical_limit,
                    snippet_length=snippet_length,
                )

        approximate_branches: list[list[MixedSearchResult]] = []
        if fuzzy_clients:
            approximate_branches.append(
                fuse_mixed_candidates(
                    clients=fuzzy_clients,
                    lexical=[],
                    semantic=[],
                    rrf_constant=rrf_constant,
                    client_weight=1.0,
                    document_lexical_weight=1.0,
                    document_semantic_weight=1.0,
                    search_decision_id=decision.decision_id,
                    excerpt_length=client_excerpt_length,
                )
            )
        if fuzzy_titles:
            approximate_branches.append(
                _fuzzy_document_results(
                    fuzzy_titles,
                    search_decision_id=decision.decision_id,
                )
            )

        spelling_fallback_used = False
        corrected_lexical: list[RetrievalCandidate] = []
        corrected_semantic: list[RetrievalCandidate] = []
        corrected_reranker_candidates: list[RetrievalCandidate] = []
        if not identifier_query and not ordinary_ranked:
            corrected_query = correct_final_token(query.text)
            if corrected_query is not None:
                spelling_fallback_used = True
                corrected_lexical = await search_lexical_candidates(
                    session,
                    tenant_id=authorization.tenant_id,
                    profile_id=profile.id,
                    query=corrected_query,
                    limit=lexical_limit,
                    snippet_length=snippet_length,
                )
                corrected_embedding: list[float] | None = None
                if mode is not RetrievalMode.LEXICAL_DEGRADED:
                    try:
                        corrected_embedding = await provider.embed_query(corrected_query)
                    except EmbeddingProviderUnavailable:
                        mode = RetrievalMode.LEXICAL_DEGRADED
                if corrected_embedding is not None:
                    corrected_semantic = await search_semantic_candidates(
                        session,
                        tenant_id=authorization.tenant_id,
                        profile_id=profile.id,
                        embedding=corrected_embedding,
                        threshold=semantic_candidate_threshold,
                        limit=semantic_limit,
                        snippet_length=snippet_length,
                    )

                corrected_reranked: list[RerankedCandidate] | None = None
                corrected_reranker_duration_ms: float | None = None
                if mode is RetrievalMode.HYBRID:
                    corrected_reranker_candidates = select_reranker_candidates(
                        corrected_lexical,
                        corrected_semantic,
                        rrf_constant=rrf_constant,
                        lexical_weight=document_lexical_weight,
                        semantic_weight=document_semantic_weight,
                        limit=reranker_limit,
                    )
                    if corrected_reranker_candidates:
                        reranker_started = time.perf_counter()
                        try:
                            corrected_scores = await reranker.rerank(
                                corrected_query,
                                [candidate.content for candidate in corrected_reranker_candidates],
                            )
                        except RerankerProviderUnavailable:
                            mode = RetrievalMode.HYBRID_UNRERANKED
                        else:
                            corrected_reranked = sorted(
                                (
                                    RerankedCandidate(candidate, score)
                                    for candidate, score in zip(
                                        corrected_reranker_candidates,
                                        corrected_scores,
                                        strict=True,
                                    )
                                    if score >= reranker_threshold
                                ),
                                key=lambda item: (-item.score, item.candidate.chunk_id.int),
                            )
                        corrected_reranker_duration_ms = (
                            time.perf_counter() - reranker_started
                        ) * 1_000
                corrected_ranked = fuse_mixed_candidates(
                    clients=[],
                    lexical=corrected_lexical,
                    semantic=corrected_semantic,
                    rrf_constant=rrf_constant,
                    client_weight=1.0,
                    document_lexical_weight=document_lexical_weight,
                    document_semantic_weight=document_semantic_weight,
                    reranked=corrected_reranked,
                    document_reranker_weight=document_reranker_weight,
                    search_decision_id=decision.decision_id,
                    excerpt_length=client_excerpt_length,
                )
                if corrected_ranked:
                    approximate_branches.append(corrected_ranked)
                if corrected_reranker_duration_ms is not None:
                    reranker_duration_ms = (reranker_duration_ms or 0.0) + (
                        corrected_reranker_duration_ms
                    )

        ranked = merge_approximate_branches(
            ordinary_ranked,
            approximate_branches,
            rrf_constant=rrf_constant,
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
        degradation_code = {
            RetrievalMode.LEXICAL_DEGRADED: "embedding_unavailable",
            RetrievalMode.HYBRID_UNRERANKED: "reranker_unavailable",
        }.get(mode)
        all_clients = [*exact_email, *exact_name, *client_lexical, *fuzzy_clients]
        all_document_candidates = [
            *lexical,
            *semantic,
            *fuzzy_titles,
            *corrected_lexical,
            *corrected_semantic,
        ]
        typed_ids = [f"{item.type.value}:{_result_identity(item)}" for item in page_results]
        rank_evidence = [
            {
                "type": item.type.value,
                "match_band": int(item.match_band),
                "client_lexical": item.ranks.client_lexical,
                "document_lexical": item.ranks.document_lexical,
                "document_semantic": item.ranks.document_semantic,
                "document_reranker": item.ranks.document_reranker,
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
                    {item.document_id for item in all_document_candidates}
                ),
                "reranker_candidate_count": len(
                    {
                        item.chunk_id
                        for item in [*reranker_candidates, *corrected_reranker_candidates]
                    }
                ),
                "reranker_model": reranker.profile.model,
                "reranker_revision": reranker.profile.model_revision,
                "reranker_duration_ms": (
                    round(reranker_duration_ms, 2) if reranker_duration_ms is not None else None
                ),
                "scores": [round(item.fused_score, 6) for item in page_results],
                "rank_evidence": rank_evidence,
                "embedding_profile_id": str(profile.id),
                "duration_ms": round(duration_ms, 2),
                "degradation_code": degradation_code,
                "spelling_fallback_used": spelling_fallback_used,
            },
        )
        logger.info(
            "mixed_search_completed",
            **search_telemetry_fields(
                mode=mode.value,
                outcome="success",
                duration_ms=duration_ms,
                lexical_candidates=len(lexical) + len(fuzzy_titles) + len(corrected_lexical),
                semantic_candidates=len(semantic) + len(corrected_semantic),
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
