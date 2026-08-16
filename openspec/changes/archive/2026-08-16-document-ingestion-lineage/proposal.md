## Why

The platform has a reproducible embedding runtime and audit foundation but no durable content to index. Plain-text ingestion is the smallest production-relevant path to establish immutable document provenance before adding untrusted file extraction or retrieval.

## What Changes

- Add a plain-text document ingestion boundary that registers a source, stable document identity, and immutable document versions within `nevis-global`.
- Add idempotent ingestion semantics based on caller-supplied idempotency keys and content hashes; identical replays must not create extra versions or indexing work.
- Add a durable PostgreSQL-backed indexing workflow that records queued, processing, completed, and failed work without placing embedding execution in the HTTP request lifecycle.
- Add deterministic text chunking and embeddings, retaining the document version, chunking configuration, embedding profile, and authorization decision for every generated chunk/vector.
- Add credential-safe audit events and operational status for ingestion and indexing outcomes.
- Explicitly exclude file upload, PDF/DOCX parsing, OCR, object storage, malware scanning, search, and tenant/advisor authorization.

## Capabilities

### New Capabilities

- `document-ingestion`: Plain-text document registration, immutable version creation, idempotency, global ownership, and audited ingestion outcomes.
- `document-indexing`: Durable indexing work, deterministic chunk/embedding generation, and lineage-preserving processing status.

### Modified Capabilities

- None.

## Impact

- Adds FastAPI ingestion and status endpoints, domain/application services, a worker processing loop, PostgreSQL tables and Alembic migration, repository operations, and API/integration tests.
- Extends the existing provider-neutral embedding contract as a consumer only; it does not add a hosted provider or change the active embedding-profile contract.
- Makes the worker an active indexing processor while retaining PostgreSQL as the durable system of record.
