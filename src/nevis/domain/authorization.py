from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

MEMBERSHIP_POLICY = "tenant-membership-v1"


class AuthorizationAction(StrEnum):
    CLIENT_CREATE = "client.create"
    CLIENT_READ = "client.read"
    CLIENT_DOCUMENT_INGEST = "client.document.ingest"
    DOCUMENT_READ = "document.read"
    DOCUMENT_INGEST = "document.ingest"  # retained for historical decisions
    DOCUMENT_VERSION_READ = "document-version.read"
    DOCUMENT_SEARCH = "document.search"
    MIXED_SEARCH = "mixed.search"


class AuthorizationDenied(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    tenant_id: UUID
    advisor_id: UUID | None
    action: AuthorizationAction
    policy: str = MEMBERSHIP_POLICY
    result: str = "allow"
    decision_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    tenant_id: UUID
    advisor_id: UUID
    decision: AuthorizationDecision
