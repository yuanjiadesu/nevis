import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, Literal

import structlog
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from nevis.application.authorization import authorize
from nevis.application.clients import create_client, retrieve_client
from nevis.application.health import readiness
from nevis.application.ingestion import (
    document_version_status,
    ingest_plain_text,
    retrieve_document,
)
from nevis.application.search import search_documents
from nevis.domain.authorization import (
    AuthorizationAction,
    AuthorizationContext,
    AuthorizationDenied,
)
from nevis.domain.clients import ClientConflict, ClientNotFound, CreateClientCommand
from nevis.domain.documents import (
    DocumentAssociationConflict,
    DocumentNotFound,
    IdempotencyConflict,
    IngestionCommand,
)
from nevis.domain.embeddings import EmbeddingProfileIdentity
from nevis.domain.identity import (
    AuthenticatedIdentity,
    IdentityCredentials,
    IdentityProvider,
    IdentityProviderUnavailable,
    InvalidIdentity,
)
from nevis.domain.search import (
    ClientSearchResult,
    InvalidSearchCursor,
    InvalidSearchQuery,
    SearchDependencyUnavailable,
    SearchQuery,
)
from nevis.infrastructure.cursors import SearchCursorCodec
from nevis.infrastructure.database import build_engine, build_session_factory
from nevis.infrastructure.embeddings import LocalTEIProvider
from nevis.infrastructure.identity import build_identity_provider
from nevis.infrastructure.logging import configure_logging
from nevis.settings import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)
BearerCredential = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]
logger = structlog.get_logger(__name__)


class IngestDocumentRequest(BaseModel):
    source_reference: str = Field(min_length=1, max_length=200)
    external_document_id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=500_000)


class IngestDocumentResponse(BaseModel):
    client_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    version_number: int
    indexing_status: str
    outcome: str


class DocumentVersionStatusResponse(BaseModel):
    document_version_id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    indexing_status: str
    queued_at: str | None
    completed_at: str | None
    failed_at: str | None
    failure_code: str | None
    chunk_count: int


class CreateClientRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=320)
    description: str | None = Field(default=None, max_length=2_000)
    social_links: list[str] = Field(default_factory=list, max_length=10)
    source_type: str = Field(min_length=1, max_length=80)
    source_reference: str = Field(min_length=1, max_length=200)


class ClientResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    description: str | None
    social_links: list[str]
    source_type: str
    source_reference: str
    creation_authorization_decision_id: uuid.UUID
    retrieval_authorization_decision_id: uuid.UUID | None
    created_at: str
    updated_at: str


class CreateClientResponse(ClientResponse):
    outcome: str


class DocumentResourceResponse(BaseModel):
    document_id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: uuid.UUID | None
    source_id: uuid.UUID
    source_reference: str
    external_document_id: str
    title: str
    current_document_version_id: uuid.UUID
    current_version_number: int
    indexing_status: str
    ingestion_authorization_decision_id: uuid.UUID
    retrieval_authorization_decision_id: uuid.UUID
    created_at: str


class SearchScoresResponse(BaseModel):
    lexical: float | None
    semantic: float | None


class SearchRanksResponse(BaseModel):
    client_lexical: int | None
    document_lexical: int | None
    document_semantic: int | None


class SearchProvenanceResponse(BaseModel):
    tenant_id: uuid.UUID
    client_id: uuid.UUID | None
    source_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    embedding_profile_id: uuid.UUID
    indexing_authorization_decision_id: uuid.UUID
    search_authorization_decision_id: uuid.UUID


class SearchResultResponse(BaseModel):
    type: Literal["document"]
    title: str
    snippet: str
    fused_score: float
    match_band: int
    scores: SearchScoresResponse
    ranks: SearchRanksResponse
    provenance: SearchProvenanceResponse


class ClientSearchProvenanceResponse(BaseModel):
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    creation_authorization_decision_id: uuid.UUID
    search_authorization_decision_id: uuid.UUID


class ClientSearchResultResponse(BaseModel):
    type: Literal["client"]
    title: str
    email: str
    excerpt: str | None
    fused_score: float
    match_band: int
    ranks: SearchRanksResponse
    provenance: ClientSearchProvenanceResponse


MixedSearchResultResponse = Annotated[
    ClientSearchResultResponse | SearchResultResponse, Field(discriminator="type")
]


class SearchResponse(BaseModel):
    ranking_version: str
    mode: str
    results: list[MixedSearchResultResponse]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class AuthenticatedRequestContext:
    identity: AuthenticatedIdentity
    tenant_slug: str
    request_id: str


async def authenticate_request(
    request: Request,
    bearer: BearerCredential,
    x_request_id: Annotated[str | None, Header(max_length=100)] = None,
    x_nevis_tenant: Annotated[str | None, Header(max_length=80)] = None,
    x_nevis_advisor: Annotated[str | None, Header(max_length=200)] = None,
) -> AuthenticatedRequestContext:
    request_id = x_request_id or str(uuid.uuid4())
    provider: IdentityProvider = request.app.state.identity_provider
    bearer_token = bearer.credentials if bearer and bearer.scheme.lower() == "bearer" else None
    try:
        identity = await provider.authenticate(
            IdentityCredentials(
                bearer_token=bearer_token,
                local_advisor_external_id=x_nevis_advisor,
            )
        )
    except InvalidIdentity as error:
        logger.info(
            "authentication_completed",
            request_id=request_id,
            identity_mode=provider.mode.value,
            outcome="invalid",
        )
        raise HTTPException(
            status_code=401,
            detail="authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except IdentityProviderUnavailable as error:
        logger.warning(
            "authentication_completed",
            request_id=request_id,
            identity_mode=provider.mode.value,
            outcome="unavailable",
        )
        raise HTTPException(status_code=503, detail="identity unavailable") from error
    logger.info(
        "authentication_completed",
        request_id=request_id,
        identity_mode=identity.mode.value,
        issuer_id=identity.issuer_id,
        outcome="authenticated",
    )
    if not x_nevis_tenant:
        raise HTTPException(status_code=401, detail="authenticated tenant context required")
    return AuthenticatedRequestContext(identity, x_nevis_tenant, request_id)


AuthenticatedRequest = Annotated[AuthenticatedRequestContext, Depends(authenticate_request)]


async def authorization_context(
    request: Request,
    *,
    authenticated: AuthenticatedRequestContext,
    action: AuthorizationAction,
) -> AuthorizationContext:
    identity = authenticated.identity
    async with request.app.state.session_factory() as session:
        try:
            context = await authorize(
                session,
                tenant_slug=authenticated.tenant_slug,
                advisor_external_id=identity.external_id,
                action=action,
                request_id=authenticated.request_id,
                identity_mode=identity.mode.value,
                identity_issuer_id=identity.issuer_id,
            )
        except AuthorizationDenied as error:
            await session.commit()
            raise HTTPException(status_code=403, detail="access denied") from error
        await session.commit()
    return context


def create_app(
    settings: Settings | None = None, identity_provider: IdentityProvider | None = None
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    engine = build_engine(resolved_settings.database_url)
    session_factory = build_session_factory(engine)
    provider = LocalTEIProvider(
        str(resolved_settings.tei_base_url),
        EmbeddingProfileIdentity(
            provider=resolved_settings.embedding_provider,
            model=resolved_settings.embedding_model,
            model_revision=resolved_settings.embedding_model_revision,
            dimensions=resolved_settings.embedding_dimensions,
            normalization=resolved_settings.embedding_normalization,
            chunking_version=resolved_settings.embedding_chunking_version,
            pipeline_version=resolved_settings.embedding_pipeline_version,
        ),
    )
    reranker = LocalTEIReranker(
        resolved_settings.reranker_base_url,
        RerankerProfileIdentity(
            provider=resolved_settings.reranker_provider,
            model=resolved_settings.reranker_model,
            model_revision=resolved_settings.reranker_model_revision,
        ),
        timeout_seconds=resolved_settings.reranker_timeout_seconds,
    )
    resolved_identity_provider = identity_provider or build_identity_provider(resolved_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        yield
        await resolved_identity_provider.aclose()
        await engine.dispose()

    app = FastAPI(title="Nevis Search Platform", version="0.1.0", lifespan=lifespan)
    app.state.session_factory = session_factory
    app.state.embedding_provider = provider
    app.state.identity_provider = resolved_identity_provider
    app.state.search_cursor_codec = SearchCursorCodec(
        resolved_settings.search_cursor_signing_key,
        resolved_settings.search_cursor_ttl_seconds,
    )
    app.state.settings = resolved_settings

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def ready(request: Request, response: Response) -> dict[str, object]:
        available, dependencies = await readiness(
            request.app.state.session_factory,
            request.app.state.embedding_provider,
            request.app.state.identity_provider,
        )
        if not available:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "ok" if available else "unavailable",
            "dependencies": {dependency.name: dependency.available for dependency in dependencies},
        }

    @app.post(
        "/v1/clients",
        status_code=status.HTTP_201_CREATED,
        response_model=CreateClientResponse,
        tags=["clients"],
    )
    async def create_client_route(
        payload: CreateClientRequest,
        request: Request,
        authenticated: AuthenticatedRequest,
        idempotency_key: str = Header(min_length=1, max_length=255),
    ) -> CreateClientResponse:
        context = await authorization_context(
            request, authenticated=authenticated, action=AuthorizationAction.CLIENT_CREATE
        )
        async with request.app.state.session_factory() as session:
            try:
                result = await create_client(
                    session,
                    CreateClientCommand(
                        first_name=payload.first_name,
                        last_name=payload.last_name,
                        email=payload.email,
                        description=payload.description,
                        social_links=tuple(payload.social_links),
                        source_type=payload.source_type,
                        source_reference=payload.source_reference,
                        idempotency_key=idempotency_key,
                        request_id=authenticated.request_id,
                    ),
                    context,
                )
            except ClientConflict as error:
                raise HTTPException(status_code=409, detail="client creation conflict") from error
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
        data = result.client
        values = {field: getattr(data, field) for field in ClientResponse.model_fields}
        values.update(
            created_at=data.created_at.isoformat(),
            updated_at=data.updated_at.isoformat(),
            outcome=result.outcome,
        )
        return CreateClientResponse(**values)

    @app.get("/v1/clients/{client_id}", response_model=ClientResponse, tags=["clients"])
    async def get_client_route(
        client_id: uuid.UUID,
        request: Request,
        authenticated: AuthenticatedRequest,
    ) -> ClientResponse:
        context = await authorization_context(
            request, authenticated=authenticated, action=AuthorizationAction.CLIENT_READ
        )
        async with request.app.state.session_factory() as session:
            try:
                data = await retrieve_client(session, client_id, context, authenticated.request_id)
            except ClientNotFound as error:
                raise HTTPException(status_code=404, detail="client not found") from error
        values = {field: getattr(data, field) for field in ClientResponse.model_fields}
        values.update(
            created_at=data.created_at.isoformat(), updated_at=data.updated_at.isoformat()
        )
        return ClientResponse(**values)

    @app.post(
        "/v1/clients/{client_id}/documents",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=IngestDocumentResponse,
        tags=["ingestion"],
    )
    async def ingest(
        client_id: uuid.UUID,
        payload: IngestDocumentRequest,
        request: Request,
        authenticated: AuthenticatedRequest,
        idempotency_key: str = Header(min_length=1, max_length=255),
    ) -> IngestDocumentResponse:
        context = await authorization_context(
            request,
            authenticated=authenticated,
            action=AuthorizationAction.CLIENT_DOCUMENT_INGEST,
        )
        async with request.app.state.session_factory() as session:
            try:
                result = await ingest_plain_text(
                    session,
                    IngestionCommand(
                        client_id=client_id,
                        source_reference=payload.source_reference,
                        external_document_id=payload.external_document_id,
                        title=payload.title,
                        content=payload.content,
                        idempotency_key=idempotency_key,
                        request_id=authenticated.request_id,
                    ),
                    request.app.state.embedding_provider.profile,
                    context,
                )
            except IdempotencyConflict as error:
                raise HTTPException(status_code=409, detail="idempotency key conflict") from error
            except DocumentAssociationConflict as error:
                raise HTTPException(
                    status_code=409, detail="document association conflict"
                ) from error
            except DocumentNotFound as error:
                raise HTTPException(status_code=404, detail="client not found") from error
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
        return IngestDocumentResponse(
            client_id=result.client_id,
            document_id=result.document_id,
            document_version_id=result.document_version_id,
            version_number=result.version_number,
            indexing_status=result.indexing_status,
            outcome=result.outcome,
        )

    @app.get(
        "/v1/documents/{document_id}",
        response_model=DocumentResourceResponse,
        tags=["documents"],
    )
    async def get_document_route(
        document_id: uuid.UUID,
        request: Request,
        authenticated: AuthenticatedRequest,
    ) -> DocumentResourceResponse:
        context = await authorization_context(
            request, authenticated=authenticated, action=AuthorizationAction.DOCUMENT_READ
        )
        async with request.app.state.session_factory() as session:
            try:
                result = await retrieve_document(
                    session, document_id, context, authenticated.request_id
                )
            except DocumentNotFound as error:
                raise HTTPException(status_code=404, detail="document not found") from error
        return DocumentResourceResponse(
            **{field: getattr(result, field) for field in DocumentResourceResponse.model_fields}
        )

    @app.get(
        "/v1/document-versions/{document_version_id}",
        response_model=DocumentVersionStatusResponse,
        tags=["ingestion"],
    )
    async def document_status(
        document_version_id: uuid.UUID,
        request: Request,
        authenticated: AuthenticatedRequest,
    ) -> DocumentVersionStatusResponse:
        context = await authorization_context(
            request,
            authenticated=authenticated,
            action=AuthorizationAction.DOCUMENT_VERSION_READ,
        )
        async with request.app.state.session_factory() as session:
            try:
                result = await document_version_status(session, document_version_id, context)
            except DocumentNotFound as error:
                raise HTTPException(status_code=404, detail="document version not found") from error
        return DocumentVersionStatusResponse(
            document_version_id=result.document_version_id,
            document_id=result.document_id,
            version_number=result.version_number,
            indexing_status=result.indexing_status,
            queued_at=result.queued_at,
            completed_at=result.completed_at,
            failed_at=result.failed_at,
            failure_code=result.failure_code,
            chunk_count=result.chunk_count,
        )

    @app.get(
        "/search",
        response_model=SearchResponse,
        tags=["search"],
        summary="Search clients and indexed documents within an authorized tenant",
    )
    async def search(
        request: Request,
        authenticated: AuthenticatedRequest,
        q: str = Query(min_length=1, max_length=2_000),
        limit: int | None = Query(default=None, ge=1, le=200),
        cursor: str | None = Query(default=None, max_length=4_096),
    ) -> SearchResponse:
        settings: Settings = request.app.state.settings
        context = await authorization_context(
            request,
            authenticated=authenticated,
            action=AuthorizationAction.MIXED_SEARCH,
        )
        try:
            search_query = SearchQuery.create(
                q,
                limit or settings.search_default_limit,
                max_length=settings.search_query_max_length,
                max_limit=settings.search_max_limit,
            )
        except InvalidSearchQuery as error:
            raise HTTPException(status_code=422, detail="invalid search query") from error
        async with request.app.state.session_factory() as session:
            try:
                page = await search_documents(
                    session,
                    query=search_query,
                    request_id=authenticated.request_id,
                    cursor=cursor,
                    authorization=context,
                    provider=request.app.state.embedding_provider,
                    reranker=request.app.state.reranker_provider,
                    cursor_codec=request.app.state.search_cursor_codec,
                    lexical_limit=settings.search_lexical_candidates,
                    semantic_limit=settings.search_semantic_candidates,
                    client_limit=settings.search_client_candidates,
                    semantic_candidate_threshold=(settings.search_semantic_candidate_threshold),
                    reranker_limit=settings.search_reranker_candidates,
                    reranker_threshold=settings.search_reranker_threshold,
                    rrf_constant=settings.search_rrf_constant,
                    snippet_length=settings.search_snippet_length,
                    client_excerpt_length=settings.search_client_description_excerpt_length,
                    client_weight=settings.search_client_weight,
                    document_lexical_weight=settings.search_document_lexical_weight,
                    document_semantic_weight=settings.search_document_semantic_weight,
                    document_reranker_weight=settings.search_document_reranker_weight,
                    ranking_version=settings.search_ranking_version,
                )
            except InvalidSearchCursor as error:
                raise HTTPException(status_code=400, detail="invalid search cursor") from error
            except (SearchDependencyUnavailable, SQLAlchemyError) as error:
                raise HTTPException(status_code=503, detail="search unavailable") from error
        return SearchResponse(
            ranking_version=page.ranking_version,
            mode=page.mode.value,
            results=[
                (
                    ClientSearchResultResponse(
                        type="client",
                        title=item.title,
                        email=item.email,
                        excerpt=item.excerpt,
                        fused_score=item.fused_score,
                        match_band=int(item.match_band),
                        ranks=SearchRanksResponse(
                            **{
                                field: getattr(item.ranks, field)
                                for field in SearchRanksResponse.model_fields
                            }
                        ),
                        provenance=ClientSearchProvenanceResponse(
                            **{
                                field: getattr(item.provenance, field)
                                for field in ClientSearchProvenanceResponse.model_fields
                            }
                        ),
                    )
                    if isinstance(item, ClientSearchResult)
                    else SearchResultResponse(
                        type="document",
                        title=item.title,
                        snippet=item.snippet,
                        fused_score=item.fused_score,
                        match_band=int(item.match_band),
                        scores=SearchScoresResponse(
                            lexical=item.scores.lexical, semantic=item.scores.semantic
                        ),
                        ranks=SearchRanksResponse(
                            **{
                                field: getattr(item.ranks, field)
                                for field in SearchRanksResponse.model_fields
                            }
                        ),
                        provenance=SearchProvenanceResponse(
                            **{
                                field: getattr(item.provenance, field)
                                for field in SearchProvenanceResponse.model_fields
                            }
                        ),
                    )
                )
                for item in page.results
            ],
            next_cursor=page.next_cursor,
        )

    return app


app = create_app()


def run() -> None:
    uvicorn.run("nevis.main:app", host="0.0.0.0", port=8000, reload=True)
