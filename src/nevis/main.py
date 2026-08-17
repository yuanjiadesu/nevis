import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated

import structlog
import uvicorn
from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from nevis.api_models import (
    ClientDocumentPageResponse,
    ClientDocumentTimelineItemResponse,
    ClientPageResponse,
    ClientResponse,
    ClientSearchProvenanceResponse,
    ClientSearchResultResponse,
    ConsoleContextResponse,
    CreateClientRequest,
    CreateClientResponse,
    DocumentEditResponse,
    DocumentResourceResponse,
    DocumentRevisionRequest,
    DocumentVersionContentResponse,
    DocumentVersionStatusResponse,
    DocumentVersionTimelineItemResponse,
    DocumentVersionTimelineResponse,
    IngestDocumentRequest,
    IngestDocumentResponse,
    SearchProvenanceResponse,
    SearchRanksResponse,
    SearchResponse,
    SearchResultResponse,
    SearchScoresResponse,
    UpdateClientRequest,
    WorkspaceSummaryResponse,
)
from nevis.application.authorization import authorize
from nevis.application.clients import (
    create_client,
    list_client_records,
    retrieve_client,
    update_client,
)
from nevis.application.health import readiness
from nevis.application.ingestion import (
    document_version_status,
    ingest_plain_text,
    list_client_documents,
    list_document_versions,
    retrieve_document,
    retrieve_document_version_content,
    retrieve_editable_document,
    revise_document,
)
from nevis.application.search import search_documents
from nevis.domain.authorization import (
    AuthorizationAction,
    AuthorizationContext,
    AuthorizationDenied,
)
from nevis.domain.clients import (
    ClientConflict,
    ClientNotFound,
    ClientUpdateConflict,
    CreateClientCommand,
    UpdateClientCommand,
)
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
    IdentityMode,
    IdentityProvider,
    IdentityProviderUnavailable,
    InvalidIdentity,
)
from nevis.domain.reranking import RerankerProfileIdentity
from nevis.domain.search import (
    ClientSearchResult,
    InvalidSearchCursor,
    InvalidSearchQuery,
    SearchDependencyUnavailable,
    SearchQuery,
)
from nevis.domain.summarization import SummaryConfiguration
from nevis.infrastructure.cursors import SearchCursorCodec
from nevis.infrastructure.database import build_engine, build_session_factory
from nevis.infrastructure.embeddings import LocalTEIProvider
from nevis.infrastructure.identity import build_identity_provider
from nevis.infrastructure.local_console import LocalConsoleCookieCodec
from nevis.infrastructure.logging import configure_logging
from nevis.infrastructure.management_cursors import (
    InvalidManagementCursor,
    ManagementCursorCodec,
    ManagementCursorState,
)
from nevis.infrastructure.repositories import (
    get_active_membership,
    get_advisor_by_external_id,
    get_global_tenant,
)
from nevis.infrastructure.reranking import LocalTEIReranker
from nevis.settings import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)
BearerCredential = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]
logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AuthenticatedRequestContext:
    identity: AuthenticatedIdentity
    tenant_slug: str
    request_id: str


async def authenticate_request(
    request: Request,
    bearer: BearerCredential,
    nevis_local_console: Annotated[str | None, Cookie(include_in_schema=False)] = None,
    x_request_id: Annotated[str | None, Header(max_length=100)] = None,
    x_nevis_tenant: Annotated[str | None, Header(max_length=80)] = None,
    x_nevis_advisor: Annotated[str | None, Header(max_length=200)] = None,
) -> AuthenticatedRequestContext:
    request_id = x_request_id or str(uuid.uuid4())
    if (
        request.app.state.settings.environment == "local"
        and request.app.state.local_console_cookie.accepts(nevis_local_console)
    ):
        return AuthenticatedRequestContext(
            AuthenticatedIdentity("local-advisor", IdentityMode.LOCAL_HEADER, "local-console"),
            "nevis-global",
            request_id,
        )
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
    tenant_slug = x_nevis_tenant
    if not tenant_slug:
        raise HTTPException(status_code=401, detail="authenticated tenant context required")
    return AuthenticatedRequestContext(identity, tenant_slug, request_id)


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
    app.state.reranker_provider = reranker
    app.state.identity_provider = resolved_identity_provider
    app.state.search_cursor_codec = SearchCursorCodec(
        resolved_settings.search_cursor_signing_key,
        resolved_settings.search_cursor_ttl_seconds,
    )
    app.state.management_cursor_codec = ManagementCursorCodec(
        resolved_settings.search_cursor_signing_key,
        resolved_settings.search_cursor_ttl_seconds,
    )
    app.state.settings = resolved_settings
    app.state.summary_configuration = SummaryConfiguration(
        enabled=resolved_settings.document_summaries_enabled,
        provider=resolved_settings.llm_provider,
        model=resolved_settings.llm_model,
        prompt_version=resolved_settings.document_summary_prompt_version,
    )
    app.state.local_console_cookie = LocalConsoleCookieCodec(
        resolved_settings.search_cursor_signing_key
    )
    workspace_directory = Path(__file__).with_name("ui") / "dist"

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ui/context", response_model=ConsoleContextResponse, tags=["workspace"])
    async def local_console_context(request: Request, response: Response) -> ConsoleContextResponse:
        if resolved_settings.environment != "local":
            raise HTTPException(status_code=404, detail="not found")
        async with request.app.state.session_factory() as session:
            advisor = await get_advisor_by_external_id(session, "local-advisor")
            if advisor is None:
                raise HTTPException(status_code=403, detail="local advisor is not provisioned")
            tenant = await get_global_tenant(session)
            membership = await get_active_membership(session, tenant.id, advisor.id)
            if membership is None:
                raise HTTPException(status_code=403, detail="local advisor has no workspace")
        response.set_cookie(
            key="nevis_local_console",
            value=request.app.state.local_console_cookie.issue(),
            httponly=True,
            samesite="lax",
            path="/",
        )
        return ConsoleContextResponse(
            advisor=advisor.external_id,
            workspace=WorkspaceSummaryResponse(slug=tenant.slug, name=tenant.name),
        )

    @app.post("/ui/logout", tags=["workspace"])
    async def local_console_logout(response: Response) -> dict[str, str]:
        if resolved_settings.environment != "local":
            raise HTTPException(status_code=404, detail="not found")
        response.delete_cookie(
            key="nevis_local_console",
            path="/",
            httponly=True,
            samesite="lax",
        )
        return {"status": "signed_out"}

    @app.get("/health/ready", tags=["health"])
    async def ready(request: Request, response: Response) -> dict[str, object]:
        available, dependencies = await readiness(
            request.app.state.session_factory,
            request.app.state.embedding_provider,
            request.app.state.identity_provider,
            request.app.state.reranker_provider,
            request.app.state.settings,
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

    @app.get("/v1/clients", response_model=ClientPageResponse, tags=["clients"])
    async def list_clients_route(
        request: Request,
        authenticated: AuthenticatedRequest,
        limit: int = Query(default=25, ge=1, le=100),
        cursor: str | None = Query(default=None, max_length=4_096),
    ) -> ClientPageResponse:
        context = await authorization_context(
            request, authenticated=authenticated, action=AuthorizationAction.CLIENT_LIST
        )
        cursor_state: ManagementCursorState | None = None
        if cursor is not None:
            try:
                cursor_state = request.app.state.management_cursor_codec.decode(
                    cursor, tenant_id=context.tenant_id, collection="clients"
                )
            except InvalidManagementCursor as error:
                raise HTTPException(status_code=400, detail="invalid client cursor") from error
        async with request.app.state.session_factory() as session:
            page = await list_client_records(
                session,
                context,
                authenticated.request_id,
                limit=limit,
                before_created_at=cursor_state.created_at if cursor_state else None,
                before_id=cursor_state.record_id if cursor_state else None,
            )
        next_cursor = None
        if page.has_more:
            last = page.clients[-1]
            next_cursor = request.app.state.management_cursor_codec.encode(
                ManagementCursorState(
                    tenant_id=context.tenant_id,
                    collection="clients",
                    created_at=last.created_at,
                    record_id=last.id,
                    issued_at=int(time.time()),
                )
            )
        return ClientPageResponse(
            clients=[
                ClientResponse(
                    **{
                        **{field: getattr(client, field) for field in ClientResponse.model_fields},
                        "created_at": client.created_at.isoformat(),
                        "updated_at": client.updated_at.isoformat(),
                    }
                )
                for client in page.clients
            ],
            next_cursor=next_cursor,
        )

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

    @app.patch("/v1/clients/{client_id}", response_model=ClientResponse, tags=["clients"])
    async def update_client_route(
        client_id: uuid.UUID,
        payload: UpdateClientRequest,
        request: Request,
        authenticated: AuthenticatedRequest,
    ) -> ClientResponse:
        context = await authorization_context(
            request, authenticated=authenticated, action=AuthorizationAction.CLIENT_UPDATE
        )
        async with request.app.state.session_factory() as session:
            try:
                data = await update_client(
                    session,
                    client_id,
                    UpdateClientCommand(
                        first_name=payload.first_name,
                        last_name=payload.last_name,
                        email=payload.email,
                        description=payload.description,
                        social_links=tuple(payload.social_links),
                        request_id=authenticated.request_id,
                    ),
                    context,
                )
            except ClientNotFound as error:
                raise HTTPException(status_code=404, detail="client not found") from error
            except ClientUpdateConflict as error:
                raise HTTPException(status_code=409, detail="client update conflict") from error
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
        return ClientResponse(
            **{
                **{field: getattr(data, field) for field in ClientResponse.model_fields},
                "created_at": data.created_at.isoformat(),
                "updated_at": data.updated_at.isoformat(),
            }
        )

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
        "/v1/clients/{client_id}/documents",
        response_model=ClientDocumentPageResponse,
        tags=["documents"],
    )
    async def client_documents_route(
        client_id: uuid.UUID,
        request: Request,
        authenticated: AuthenticatedRequest,
        limit: int = Query(default=25, ge=1, le=100),
        cursor: str | None = Query(default=None, max_length=4_096),
    ) -> ClientDocumentPageResponse:
        context = await authorization_context(
            request,
            authenticated=authenticated,
            action=AuthorizationAction.CLIENT_DOCUMENT_LIST,
        )
        cursor_state: ManagementCursorState | None = None
        if cursor is not None:
            try:
                cursor_state = request.app.state.management_cursor_codec.decode(
                    cursor, tenant_id=context.tenant_id, collection=f"client-documents:{client_id}"
                )
            except InvalidManagementCursor as error:
                raise HTTPException(status_code=400, detail="invalid document cursor") from error
        async with request.app.state.session_factory() as session:
            try:
                documents, has_more = await list_client_documents(
                    session,
                    client_id,
                    context,
                    authenticated.request_id,
                    limit=limit,
                    before_created_at=cursor_state.created_at if cursor_state else None,
                    before_id=cursor_state.record_id if cursor_state else None,
                )
            except DocumentNotFound as error:
                raise HTTPException(status_code=404, detail="client not found") from error
        next_cursor = None
        if has_more:
            last = documents[-1]
            next_cursor = request.app.state.management_cursor_codec.encode(
                ManagementCursorState(
                    tenant_id=context.tenant_id,
                    collection=f"client-documents:{client_id}",
                    created_at=datetime.fromisoformat(last.created_at),
                    record_id=last.document_id,
                    issued_at=int(time.time()),
                )
            )
        return ClientDocumentPageResponse(
            documents=[
                ClientDocumentTimelineItemResponse(
                    **{
                        field: getattr(document, field)
                        for field in ClientDocumentTimelineItemResponse.model_fields
                    }
                )
                for document in documents
            ],
            next_cursor=next_cursor,
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
                    session,
                    document_id,
                    context,
                    authenticated.request_id,
                )
            except DocumentNotFound as error:
                raise HTTPException(status_code=404, detail="document not found") from error
        return DocumentResourceResponse(
            **{field: getattr(result, field) for field in DocumentResourceResponse.model_fields}
        )

    @app.get(
        "/v1/documents/{document_id}/edit",
        response_model=DocumentEditResponse,
        tags=["documents"],
    )
    async def document_edit_route(
        document_id: uuid.UUID,
        request: Request,
        authenticated: AuthenticatedRequest,
    ) -> DocumentEditResponse:
        context = await authorization_context(
            request, authenticated=authenticated, action=AuthorizationAction.DOCUMENT_EDIT
        )
        async with request.app.state.session_factory() as session:
            try:
                result = await retrieve_editable_document(
                    session, document_id, context, authenticated.request_id
                )
            except DocumentNotFound as error:
                raise HTTPException(status_code=404, detail="document not found") from error
        return DocumentEditResponse(
            document_id=result.document_id,
            client_id=result.client_id,
            title=result.title,
            content=result.content,
            current_document_version_id=result.current_document_version_id,
            current_version_number=result.current_version_number,
        )

    @app.post(
        "/v1/documents/{document_id}/revisions",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=IngestDocumentResponse,
        tags=["ingestion"],
    )
    async def document_revision_route(
        document_id: uuid.UUID,
        payload: DocumentRevisionRequest,
        request: Request,
        authenticated: AuthenticatedRequest,
        idempotency_key: str = Header(min_length=1, max_length=255),
    ) -> IngestDocumentResponse:
        context = await authorization_context(
            request, authenticated=authenticated, action=AuthorizationAction.DOCUMENT_REVISE
        )
        async with request.app.state.session_factory() as session:
            try:
                result = await revise_document(
                    session,
                    document_id,
                    title=payload.title,
                    content=payload.content,
                    idempotency_key=idempotency_key,
                    profile_identity=request.app.state.embedding_provider.profile,
                    authorization=context,
                    request_id=authenticated.request_id,
                    summary_configuration=request.app.state.summary_configuration,
                )
            except DocumentNotFound as error:
                raise HTTPException(status_code=404, detail="document not found") from error
            except DocumentAssociationConflict as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            except IdempotencyConflict as error:
                raise HTTPException(status_code=409, detail="idempotency key conflict") from error
            except IntegrityError as error:
                raise HTTPException(status_code=409, detail="ingestion conflict") from error
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
        "/v1/documents/{document_id}/versions",
        response_model=DocumentVersionTimelineResponse,
        tags=["documents"],
    )
    async def document_versions_route(
        document_id: uuid.UUID,
        request: Request,
        authenticated: AuthenticatedRequest,
    ) -> DocumentVersionTimelineResponse:
        context = await authorization_context(
            request,
            authenticated=authenticated,
            action=AuthorizationAction.DOCUMENT_VERSION_LIST,
        )
        async with request.app.state.session_factory() as session:
            try:
                versions = await list_document_versions(
                    session, document_id, context, authenticated.request_id
                )
            except DocumentNotFound as error:
                raise HTTPException(status_code=404, detail="document not found") from error
        return DocumentVersionTimelineResponse(
            versions=[
                DocumentVersionTimelineItemResponse(
                    **{
                        field: getattr(version, field)
                        for field in DocumentVersionTimelineItemResponse.model_fields
                    }
                )
                for version in versions
            ]
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
        "/v1/document-versions/{document_version_id}/content",
        response_model=DocumentVersionContentResponse,
        tags=["documents"],
    )
    async def document_version_content_route(
        document_version_id: uuid.UUID,
        request: Request,
        authenticated: AuthenticatedRequest,
    ) -> DocumentVersionContentResponse:
        context = await authorization_context(
            request,
            authenticated=authenticated,
            action=AuthorizationAction.DOCUMENT_VERSION_CONTENT_READ,
        )
        async with request.app.state.session_factory() as session:
            try:
                result = await retrieve_document_version_content(
                    session, document_version_id, context, authenticated.request_id
                )
            except DocumentNotFound as error:
                raise HTTPException(status_code=404, detail="document version not found") from error
        return DocumentVersionContentResponse(
            document_version_id=result.document_version_id,
            document_id=result.document_id,
            version_number=result.version_number,
            content=result.content,
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
                        client_name=item.client_name,
                        snippet=item.snippet,
                        fused_score=item.fused_score,
                        match_band=int(item.match_band),
                        scores=SearchScoresResponse(
                            lexical=item.scores.lexical,
                            semantic=item.scores.semantic,
                            reranker=item.scores.reranker,
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

    app.mount(
        "/assets", StaticFiles(directory=workspace_directory / "assets"), name="workspace-assets"
    )

    @app.get("/favicon.svg", include_in_schema=False, response_model=None)
    async def favicon() -> FileResponse:
        if resolved_settings.environment != "local":
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(workspace_directory / "favicon.svg", media_type="image/svg+xml")

    @app.get("/", include_in_schema=False, response_model=None)
    async def workspace() -> FileResponse:
        if resolved_settings.environment != "local":
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(
            workspace_directory / "index.html", headers={"Cache-Control": "no-store"}
        )

    return app


def run() -> None:
    uvicorn.run("nevis.main:create_app", factory=True, host="0.0.0.0", port=8000, reload=True)
