import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlparse


class ClientError(Exception):
    """A credential- and PII-safe client operation failure."""


class ClientConflict(ClientError):
    pass


class ClientNotFound(ClientError):
    pass


class ClientCreationOutcome(StrEnum):
    CREATED = "created"
    REPLAYED = "replayed"


def normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized or len(normalized) > 320 or normalized.count("@") != 1:
        raise ValueError("email must be a valid bounded address")
    local, domain = normalized.split("@")
    if not local or not domain or "." not in domain:
        raise ValueError("email must be a valid bounded address")
    return normalized


def validate_social_links(values: tuple[str, ...]) -> tuple[str, ...]:
    if len(values) > 10:
        raise ValueError("social_links must contain at most 10 links")
    result: list[str] = []
    for value in values:
        link = value.strip()
        parsed = urlparse(link)
        if len(link) > 500 or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("social_links must contain bounded HTTP(S) URLs")
        result.append(link)
    if len(json.dumps(result)) > 5_500:
        raise ValueError("social_links are too large")
    return tuple(result)


@dataclass(frozen=True, slots=True)
class CreateClientCommand:
    first_name: str
    last_name: str
    email: str
    description: str | None
    social_links: tuple[str, ...]
    source_type: str
    source_reference: str
    idempotency_key: str
    request_id: str

    def normalized(self) -> "CreateClientCommand":
        first_name = self.first_name.strip()
        last_name = self.last_name.strip()
        source_type = self.source_type.strip()
        source_reference = self.source_reference.strip()
        description = self.description.strip() if self.description else None
        if not first_name or len(first_name) > 100 or not last_name or len(last_name) > 100:
            raise ValueError("first_name and last_name are required and bounded")
        if (
            not source_type
            or len(source_type) > 80
            or not source_reference
            or len(source_reference) > 200
        ):
            raise ValueError("source provenance is required and bounded")
        if description is not None and len(description) > 2_000:
            raise ValueError("description is too long")
        if not self.idempotency_key or len(self.idempotency_key) > 255:
            raise ValueError("idempotency key is required and bounded")
        return CreateClientCommand(
            first_name,
            last_name,
            normalize_email(self.email),
            description,
            validate_social_links(self.social_links),
            source_type,
            source_reference,
            self.idempotency_key,
            self.request_id,
        )


def client_request_fingerprint(command: CreateClientCommand) -> str:
    normalized = command.normalized()
    canonical = json.dumps(
        {
            "description": normalized.description,
            "email": normalized.email,
            "first_name": normalized.first_name,
            "last_name": normalized.last_name,
            "social_links": normalized.social_links,
            "source_reference": normalized.source_reference,
            "source_type": normalized.source_type,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ClientResource:
    id: uuid.UUID
    tenant_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    description: str | None
    social_links: tuple[str, ...]
    source_type: str
    source_reference: str
    creation_authorization_decision_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    retrieval_authorization_decision_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ClientCreationResult:
    client: ClientResource
    outcome: ClientCreationOutcome
