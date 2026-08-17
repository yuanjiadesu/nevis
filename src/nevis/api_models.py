import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from nevis.domain.summarization import SummaryStatus


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


class DocumentRevisionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=500_000)


class DocumentEditResponse(BaseModel):
    document_id: uuid.UUID
    client_id: uuid.UUID | None
    title: str
    content: str
    current_document_version_id: uuid.UUID
    current_version_number: int


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


class DocumentVersionContentResponse(BaseModel):
    document_version_id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    content: str


class CreateClientRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=320)
    description: str | None = Field(default=None, max_length=2_000)
    social_links: list[str] = Field(default_factory=list, max_length=10)
    source_type: str = Field(min_length=1, max_length=80)
    source_reference: str = Field(min_length=1, max_length=200)


class UpdateClientRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=320)
    description: str | None = Field(default=None, max_length=2_000)
    social_links: list[str] = Field(default_factory=list, max_length=10)


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


class ClientPageResponse(BaseModel):
    clients: list[ClientResponse]
    next_cursor: str | None


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
    summary_status: SummaryStatus
    summary: str | None


class ClientDocumentTimelineItemResponse(BaseModel):
    document_id: uuid.UUID
    client_id: uuid.UUID
    title: str
    current_document_version_id: uuid.UUID
    current_version_number: int
    indexing_status: str
    created_at: str
    summary_status: SummaryStatus
    summary: str | None


class ClientDocumentPageResponse(BaseModel):
    documents: list[ClientDocumentTimelineItemResponse]
    next_cursor: str | None


class DocumentVersionTimelineItemResponse(BaseModel):
    document_version_id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    indexing_status: str
    created_at: str


class DocumentVersionTimelineResponse(BaseModel):
    versions: list[DocumentVersionTimelineItemResponse]


class SearchScoresResponse(BaseModel):
    lexical: float | None
    semantic: float | None
    reranker: float | None


class SearchRanksResponse(BaseModel):
    client_lexical: int | None
    document_lexical: int | None
    document_semantic: int | None
    document_reranker: int | None


class SearchProvenanceResponse(BaseModel):
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    source_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    embedding_profile_id: uuid.UUID
    indexing_authorization_decision_id: uuid.UUID
    search_authorization_decision_id: uuid.UUID


class SearchResultResponse(BaseModel):
    type: Literal["document"]
    title: str
    client_name: str
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


class WorkspaceSummaryResponse(BaseModel):
    slug: str
    name: str


class ConsoleContextResponse(BaseModel):
    advisor: str
    workspace: WorkspaceSummaryResponse
