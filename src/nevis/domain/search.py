import hashlib
import re
import uuid
from dataclasses import dataclass
from enum import IntEnum, StrEnum

MIXED_RANKING_VERSION = "mixed-rrf-v1"


class RetrievalMode(StrEnum):
    HYBRID = "hybrid"
    LEXICAL_DEGRADED = "lexical_degraded"


class ResultType(StrEnum):
    CLIENT = "client"
    DOCUMENT = "document"


class MatchBand(IntEnum):
    EXACT_EMAIL = 0
    EXACT_NAME = 1
    GENERAL = 2


class SearchError(Exception):
    """Base class for credential-safe search failures."""


class InvalidSearchQuery(SearchError):
    pass


class InvalidSearchCursor(SearchError):
    pass


class SearchDependencyUnavailable(SearchError):
    pass


@dataclass(frozen=True, slots=True)
class SearchQuery:
    text: str
    limit: int

    @classmethod
    def create(cls, text: str, limit: int, *, max_length: int, max_limit: int) -> "SearchQuery":
        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized or len(normalized) > max_length or not 1 <= limit <= max_limit:
            raise InvalidSearchQuery("invalid search query")
        return cls(text=normalized, limit=limit)

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.text.casefold().encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ComponentScores:
    lexical: float | None
    semantic: float | None


@dataclass(frozen=True, slots=True)
class BranchRanks:
    client_lexical: int | None = None
    document_lexical: int | None = None
    document_semantic: int | None = None


@dataclass(frozen=True, slots=True)
class DocumentSearchProvenance:
    tenant_id: uuid.UUID
    client_id: uuid.UUID | None
    source_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    embedding_profile_id: uuid.UUID
    indexing_authorization_decision_id: uuid.UUID
    search_authorization_decision_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class SearchResult:
    type: ResultType
    title: str
    snippet: str
    fused_score: float
    match_band: MatchBand
    scores: ComponentScores
    ranks: BranchRanks
    provenance: DocumentSearchProvenance


@dataclass(frozen=True, slots=True)
class ClientSearchProvenance:
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    creation_authorization_decision_id: uuid.UUID
    search_authorization_decision_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ClientSearchResult:
    type: ResultType
    title: str
    email: str
    excerpt: str | None
    fused_score: float
    match_band: MatchBand
    ranks: BranchRanks
    provenance: ClientSearchProvenance


MixedSearchResult = ClientSearchResult | SearchResult


@dataclass(frozen=True, slots=True)
class SearchPage:
    ranking_version: str
    mode: RetrievalMode
    results: tuple[MixedSearchResult, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    tenant_id: uuid.UUID
    client_id: uuid.UUID | None
    source_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    embedding_profile_id: uuid.UUID
    indexing_authorization_decision_id: uuid.UUID
    title: str
    snippet: str
    score: float


@dataclass(frozen=True, slots=True)
class ClientRetrievalCandidate:
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    description: str | None
    creation_authorization_decision_id: uuid.UUID
    match_band: MatchBand
    score: float


@dataclass(frozen=True, slots=True)
class CursorState:
    query_fingerprint: str
    tenant_id: uuid.UUID
    embedding_profile_id: uuid.UUID
    mode: RetrievalMode
    ranking_version: str
    match_band: MatchBand
    fused_score: float
    result_type: ResultType
    result_id: uuid.UUID
    issued_at: int
