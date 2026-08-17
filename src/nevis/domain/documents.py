import hashlib
import re
import uuid
from dataclasses import dataclass
from enum import StrEnum

from nevis.domain.summarization import SummaryStatus


class IndexingStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionOutcome(StrEnum):
    ACCEPTED = "accepted"
    REPLAYED = "replayed"


class IngestionError(Exception):
    """A safe, client-visible ingestion failure."""


class IdempotencyConflict(IngestionError):
    pass


class DocumentNotFound(IngestionError):
    pass


class DocumentAssociationConflict(IngestionError):
    pass


@dataclass(frozen=True, slots=True)
class IngestionCommand:
    client_id: uuid.UUID
    source_reference: str
    external_document_id: str
    title: str
    content: str
    idempotency_key: str
    request_id: str


@dataclass(frozen=True, slots=True)
class IngestionResult:
    client_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    version_number: int
    indexing_status: IndexingStatus
    outcome: IngestionOutcome


@dataclass(frozen=True, slots=True)
class DocumentVersionStatus:
    document_version_id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    indexing_status: IndexingStatus
    queued_at: str | None
    completed_at: str | None
    failed_at: str | None
    failure_code: str | None
    chunk_count: int


@dataclass(frozen=True, slots=True)
class DocumentVersionContent:
    document_version_id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    content: str


@dataclass(frozen=True, slots=True)
class DocumentResource:
    document_id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    source_id: uuid.UUID
    source_reference: str
    external_document_id: str
    title: str
    current_document_version_id: uuid.UUID
    current_version_number: int
    indexing_status: IndexingStatus
    ingestion_authorization_decision_id: uuid.UUID
    retrieval_authorization_decision_id: uuid.UUID
    created_at: str
    summary_status: SummaryStatus
    summary: str | None


@dataclass(frozen=True, slots=True)
class EditableDocument:
    document_id: uuid.UUID
    client_id: uuid.UUID
    source_reference: str
    external_document_id: str
    title: str
    content: str
    current_document_version_id: uuid.UUID
    current_version_number: int


@dataclass(frozen=True, slots=True)
class DocumentTimelineItem:
    document_id: uuid.UUID
    client_id: uuid.UUID
    title: str
    current_document_version_id: uuid.UUID
    current_version_number: int
    indexing_status: IndexingStatus
    created_at: str
    summary_status: SummaryStatus
    summary: str | None


@dataclass(frozen=True, slots=True)
class DocumentVersionTimelineItem:
    document_version_id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    indexing_status: IndexingStatus
    created_at: str


@dataclass(frozen=True, slots=True)
class ChunkingConfiguration:
    version: int
    window_size: int
    overlap: int


DEFAULT_CHUNKING = ChunkingConfiguration(version=1, window_size=1_000, overlap=200)


def normalize_text(content: str) -> str:
    """Canonicalize line endings and incidental whitespace without changing words."""
    return re.sub(r"[ \t]+\n", "\n", content.replace("\r\n", "\n").replace("\r", "\n")).strip()


def content_hash(content: str) -> str:
    return hashlib.sha256(normalize_text(content).encode("utf-8")).hexdigest()


def request_fingerprint(command: IngestionCommand) -> str:
    canonical = "\x1f".join(
        (
            str(command.client_id),
            command.source_reference.strip(),
            command.external_document_id.strip(),
            command.title.strip(),
            content_hash(command.content),
        )
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def chunk_text(
    content: str, configuration: ChunkingConfiguration = DEFAULT_CHUNKING
) -> list[tuple[int, int, str]]:
    normalized = normalize_text(content)
    if not normalized:
        return []
    chunks: list[tuple[int, int, str]] = []
    start = 0
    while start < len(normalized):
        end = min(start + configuration.window_size, len(normalized))
        chunks.append((start, end, normalized[start:end]))
        if end == len(normalized):
            break
        start = end - configuration.overlap
    return chunks
