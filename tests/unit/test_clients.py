import uuid

import pytest

from nevis.domain.clients import (
    CreateClientCommand,
    client_request_fingerprint,
    normalize_email,
)
from nevis.domain.documents import IngestionCommand, request_fingerprint


def command(**changes: object) -> CreateClientCommand:
    values = {
        "first_name": " Ada ",
        "last_name": " Lovelace ",
        "email": " Ada@Example.COM ",
        "description": " First programmer ",
        "social_links": ("https://example.com/ada",),
        "source_type": "crm",
        "source_reference": "contact-1",
        "idempotency_key": "key-1",
        "request_id": "request-1",
    }
    values.update(changes)
    return CreateClientCommand(**values)  # type: ignore[arg-type]


def test_client_normalization_and_fingerprint_are_deterministic() -> None:
    normalized = command().normalized()
    assert normalize_email(" Ada@Example.COM ") == "ada@example.com"
    assert normalized.first_name == "Ada"
    assert normalized.description == "First programmer"
    assert client_request_fingerprint(command()) == client_request_fingerprint(normalized)
    assert client_request_fingerprint(
        command(idempotency_key="another")
    ) == client_request_fingerprint(command())


@pytest.mark.parametrize("email", ["", "missing-at", "a@localhost"])
def test_invalid_email_is_rejected(email: str) -> None:
    with pytest.raises(ValueError):
        command(email=email).normalized()


def test_social_links_are_bounded_and_http_only() -> None:
    with pytest.raises(ValueError):
        command(social_links=("javascript:alert(1)",)).normalized()
    with pytest.raises(ValueError):
        command(
            social_links=tuple(f"https://example.com/{index}" for index in range(11))
        ).normalized()


def test_ingestion_fingerprint_includes_client_identity() -> None:
    base = dict(
        source_reference="crm",
        external_document_id="doc",
        title="Title",
        content="Text",
        idempotency_key="key",
        request_id="request",
    )
    first = IngestionCommand(client_id=uuid.uuid4(), **base)
    second = IngestionCommand(client_id=uuid.uuid4(), **base)
    assert request_fingerprint(first) != request_fingerprint(second)
