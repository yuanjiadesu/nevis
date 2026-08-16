import uuid

from nevis.domain.documents import (
    DEFAULT_CHUNKING,
    IngestionCommand,
    chunk_text,
    content_hash,
    normalize_text,
    request_fingerprint,
)


def test_normalization_hash_and_fingerprint_are_deterministic() -> None:
    command = IngestionCommand(
        client_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        source_reference="crm",
        external_document_id="client-1",
        title="Proof of address",
        content="A line\r\nAnother line  \n",
        idempotency_key="not-part-of-fingerprint",
        request_id="request-1",
    )

    assert normalize_text(command.content) == "A line\nAnother line"
    assert content_hash(command.content) == content_hash("A line\nAnother line")
    assert request_fingerprint(command) == request_fingerprint(command)


def test_chunking_is_ordered_and_repeatable() -> None:
    content = "x" * (DEFAULT_CHUNKING.window_size + 20)

    chunks = chunk_text(content)

    assert chunks == chunk_text(content)
    assert chunks[0][:2] == (0, DEFAULT_CHUNKING.window_size)
    assert chunks[1][0] == DEFAULT_CHUNKING.window_size - DEFAULT_CHUNKING.overlap
    assert chunks[1][1] == len(content)
