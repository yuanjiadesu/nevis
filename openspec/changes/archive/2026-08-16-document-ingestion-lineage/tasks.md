## 1. Domain contract and persistence model

- [x] 1.1 Define typed ingestion, document-version, indexing-status, and safe failure domain contracts.
- [x] 1.2 Define deterministic text normalization, hashing, and chunking configuration utilities with explicit version identifiers.
- [x] 1.3 Add source, document, document-version, idempotency-record, indexing-job, and document-chunk/vector persistence models with lineage fields and constraints.
- [x] 1.4 Add an additive Alembic migration with pgvector dimensions, foreign keys, uniqueness constraints, indexes, and a safe downgrade for empty local/test data.
- [x] 1.5 Implement repository operations for immutable version creation, idempotency lookup/conflict detection, job lifecycle transitions, and status reads without application update/delete operations for versions or chunks.

## 2. Ingestion application and API boundary

- [x] 2.1 Implement the transactional ingestion use case that creates global-scope source/document/version, audit event, and queued indexing job atomically.
- [x] 2.2 Implement replay and conflicting-idempotency behavior, including safe audit metadata for accepted, rejected, and replayed requests.
- [x] 2.3 Add Pydantic request/response models and FastAPI routes for plain-text ingestion and document-version status.
- [x] 2.4 Enforce plain-text JSON validation, size/chunk configuration limits, and safe error responses; reject file/binary multipart submissions.
- [x] 2.5 Ensure API logging and telemetry exclude document content, chunk text, idempotency keys, and provider credentials.

## 3. Durable indexing worker

- [x] 3.1 Implement PostgreSQL job claiming with leases, attempt tracking, expiry recovery, and safe queued/processing/completed/failed transitions.
- [x] 3.2 Resolve and persist the active immutable embedding-profile identity when indexing work is created, then use it for every processing attempt.
- [x] 3.3 Implement deterministic chunk persistence with ordered boundaries and content hashes, protected from duplicate retry writes.
- [x] 3.4 Implement provider-neutral batch embedding and lineage-preserving vector persistence for every chunk.
- [x] 3.5 Implement worker polling, graceful shutdown, retry classification, and credential-safe audit/telemetry events for indexing outcomes.

## 4. Verification and operational integration

- [x] 4.1 Add unit tests for normalization, content hashing, deterministic chunking, idempotency, and safe failure/telemetry redaction.
- [x] 4.2 Add database integration tests for migration upgrade/downgrade, immutable document versions, global ownership, idempotency replay/conflict, job leasing, retry safety, and complete vector provenance.
- [x] 4.3 Add API tests for accepted ingestion, changed-content versions, replay/conflict responses, status visibility, and unsupported file/binary requests.
- [x] 4.4 Add worker tests with the deterministic fake embedding provider for success, provider failure, and interrupted-work recovery without cloud credentials.
- [x] 4.5 Extend the Compose smoke test and CI to ingest a fixture, wait for completed indexing, and assert status plus source/document/version/profile/authorization provenance.

## 5. Documentation and change validation

- [x] 5.1 Update the README with the trusted plain-text ingestion contract, local fixture workflow, status endpoint, and explicit file-ingestion/search exclusions.
- [x] 5.2 Update the runbook with indexing failure diagnosis, safe retry guidance, local test-data reset, and lineage inspection queries.
- [x] 5.3 Verify format, lint, type checks, all tests, Alembic migration validation, Compose smoke test, and strict OpenSpec validation.
- [x] 5.4 Confirm the implementation provides no file upload/extraction, search/retrieval endpoint, or tenant/advisor authorization behavior.
