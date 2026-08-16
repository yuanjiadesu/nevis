## Context

See `proposal.md` for the motivation. The existing platform has `nevis-global`, append-only audit events, a persisted active embedding profile, local TEI, and an independently runnable worker; it intentionally has no document records or business endpoints. The main lineage specs require later results to be attributable to organization, source, document version, embedding profile, and authorization decision.

## Goals / Non-Goals

**Goals:**

- Add a durable plain-text ingestion boundary whose successful result is an immutable, versioned document.
- Make indexing asynchronous, recoverable, idempotent, and inspectable without adding a second durable service.
- Persist enough lineage at write time that future retrieval cannot lose document and authorization provenance.
- Retain safe operational signals without logging raw document or chunk content.

**Non-Goals:**

- File storage, PDF/DOCX parsing, OCR, malware scanning, or binary uploads.
- Search, ranking, retrieval, client/advisor authentication, tenant filtering, or access enforcement beyond the existing global decision.
- Hosted embedding adapters, vector re-embedding migrations, or a general-purpose workflow engine.

## Decisions

### Plain-text JSON API with explicit idempotency

Expose a versioned plain-text ingestion endpoint and a document-version status endpoint. The ingestion request carries a source reference, external document identifier, title, content, and an idempotency key; content and idempotency keys are never emitted in logs or audit metadata. The API creates a source on first reference, resolves a stable document identity, and returns the immutable version ID and its indexing state.

The request's canonical fingerprint is stored with the idempotency key. Replaying it returns the original outcome; reusing the key with a distinct fingerprint is rejected. Content normalization and SHA-256 hashing distinguish a genuine new version from a replay.

**Alternatives considered:** An internal CLI avoids an HTTP contract but would defer a core integration boundary. Accepting uploads now would entangle ingestion with untrusted-binary security and extraction reliability.

### Versioned relational lineage model

Add `document_sources`, `documents`, `document_versions`, `indexing_jobs`, and `document_chunks` as PostgreSQL records. Sources and documents carry organization ownership; versions are immutable and sequence-numbered per document. A version retains canonical plain text only in the data store, its normalized hash, and the global authorization-policy/result snapshot.

Chunks are immutable children of a version and retain ordinal, character start/end, content hash, active embedding-profile ID, embedding vector, and copied provenance fields. Unique constraints cover source/document identity, version number, idempotency key, job identity, and chunk/vector identity so the database enforces retry safety.

**Alternatives considered:** A separate vector store would split atomic lineage across systems before retrieval exists. Storing only foreign keys reduces duplication but risks losing point-in-time authorization/profile attribution when referenced records evolve; copied provenance fields preserve the evidence while foreign keys retain referential integrity.

### Transactional outbox-style PostgreSQL job queue

The ingestion transaction writes the document version, audit event, and queued indexing job together. The worker leases queued work with row locking, records processing attempts, and moves work to completed or failed with a safe error category. A lease expiry allows recovery after worker interruption; retries rebuild the version's chunk/vector set under database uniqueness constraints.

**Alternatives considered:** Framework background tasks are not durable and couple acceptance to process lifetime. Redis/Celery adds infrastructure and delivery semantics that are unnecessary before workload scale demands them.

### Deterministic chunking and active-profile embedding

Use a named, versioned deterministic chunking configuration (fixed normalization, window, and overlap) and make the job resolve the active persisted embedding profile before embedding. The worker uses the existing provider-neutral contract; it never embeds in the request handler. A completed job is only recorded after all chunks and vectors have been persisted for the same version/profile identity.

**Alternatives considered:** Provider-specific orchestration would undermine the existing portability boundary. Semantic/adaptive chunking may improve recall later but is harder to reproduce and evaluate in the initial data pipeline.

### Audit and status surfaces

Emit append-only audit events for accepted, rejected, replayed, started, completed, and failed ingestion/indexing outcomes. Status responses expose IDs, lifecycle timestamps, counts, and safe error classes only. Structured telemetry uses document/version IDs and hashes/counts rather than raw input.

**Alternatives considered:** Logging raw text simplifies debugging but violates the platform's privacy posture and makes operational systems a data-exposure surface.

## Risks / Trade-offs

- [Persisting plain text in PostgreSQL increases sensitive-data responsibility] → restrict the boundary to trusted internal callers for this global-scope release, avoid telemetry content, and introduce encryption/retention policy with the file-ingestion/auth changes.
- [A PostgreSQL job queue has bounded throughput] → use leasing and `SKIP LOCKED` now; introduce a dedicated queue only after measured throughput requires it.
- [Fixed chunking may not optimize retrieval quality] → version the configuration and record it with every vector so a future re-index can be compared and traced.
- [Active embedding profile could change while a job waits] → resolve and persist the profile at job creation, then use that immutable profile for every attempt.
- [Idempotency keys can be retained indefinitely] → make retention a future policy decision; do not delete records in this foundation phase.

## Migration Plan

1. Add tables, indexes, vector columns, and constraints in an additive Alembic migration; preserve the existing global organization and audit tables.
2. Deploy API and worker code compatible with the new schema, then run the migration before enabling the API endpoint.
3. Verify a plain-text submission creates a version and queued job atomically; verify worker completion produces chunks/vectors and audit events.
4. Roll back by disabling ingestion/worker processing and restoring the previous application image. The migration downgrade is for empty local/test environments only; production data is forward-only once documents are accepted.

## Open Questions

- Maximum plain-text size and per-version chunk limits will be set as operational configuration during implementation; they do not alter the lifecycle or lineage contract.
