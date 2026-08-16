## Context

The service already has tenant and advisor membership authorization, immutable document/version lineage, idempotent ingestion, durable indexing, and tenant-filtered document search. Documents currently have no client foreign key, the only document resource endpoint addresses a version, and `POST /v1/documents` accepts unassociated documents. See `proposal.md` for motivation and the four delta specs for observable behavior.

The migration must preserve existing test, development, and any deployed document lineage. The design should deepen the modular monolith rather than add services or dependencies.

## Goals / Non-Goals

**Goals:**

- Add the client aggregate and client/document ownership relation without changing the indexing worker or embedding contract.
- Keep all client and document lookups tenant-scoped in the database query itself.
- Make create operations race-safe, retry-safe, auditable, and free of raw PII in operational records.
- Establish API representations that can later become the inputs to mixed search.

**Non-Goals:**

- Client update/delete, document reassignment, bulk import, search, fuzzy matching, or mixed ranking.
- Advisor-specific ownership below the existing tenant membership policy.
- Backfilling legacy documents to invented clients or enforcing a database-wide non-null client key in this migration.
- Changing chunking, embeddings, worker claiming, document search ranking, or OIDC behavior.

## Decisions

### 1. Use a tenant-owned client aggregate with explicit normalized email

Add `clients` with `id`, `tenant_id`, bounded names, `email`, `normalized_email`, optional description, bounded JSON social links, `source_type`, `source_ref`, `creation_authorization_decision_id`, and timestamps. Enforce `UNIQUE (tenant_id, normalized_email)` in PostgreSQL. Application normalization trims the address and lowercases it using one versioned rule before validation, persistence, fingerprinting, and comparison; the database constraint is the concurrency backstop.

Keeping both display and normalized values avoids PostgreSQL `citext` as a new extension and makes the identity rule explicit. A functional `lower(email)` index was considered, but a stored normalized value is easier to fingerprint, inspect, and keep consistent across callers.

Social links are stored as a bounded list of validated HTTP(S) URLs and are not indexed in this change. Source fields are explicit client provenance, not connector behavior.

### 2. Use a dedicated client-creation idempotency record

Add `client_creation_requests` keyed by `(tenant_id, idempotency_key)` with the normalized request fingerprint and resulting client identity. The service checks it inside the creation transaction, returns the original record for an identical replay, and returns `409` for a different fingerprint. Database uniqueness on both the idempotency key and normalized email handles concurrent submissions; expected integrity conflicts are translated to stable API outcomes.

Reusing `ingestion_requests` was rejected because its result and lifecycle are document-version-specific. A generic idempotency framework is unnecessary until a third write workflow demonstrates a stable shared abstraction.

### 3. Make nested client-scoped ingestion the only new-ingestion contract

Replace `POST /v1/documents` with `POST /v1/clients/{client_id}/documents`. Resolve the client using both `client_id` and the already-authorized `tenant_id` before creating any ingestion state. Add nullable `documents.client_id` plus an index beginning with `tenant_id`; application code requires it for new documents.

When an existing `(tenant_id, source_id, external_document_id)` is updated, its stored client must equal the path client. The client identity becomes part of the ingestion fingerprint, so retries cannot silently reassign a document. Document-to-client reassignment is intentionally unsupported.

Keeping the old unscoped route was considered, but it would preserve a path that bypasses the product's client ownership invariant. This is a deliberate pre-release breaking API correction.

### 4. Preserve legacy documents with an explicit nullable association

The migration adds `documents.client_id` as nullable and does not fabricate client records. Existing documents remain searchable and retrievable with `client_id: null`; every new ingestion must supply a real same-tenant client. A later operational backfill and non-null constraint can be proposed if a deployment actually contains legacy data requiring remediation.

Creating one synthetic client per tenant was rejected because it invents business data and can distort later client search. Making the column immediately non-null would make a safe generic upgrade impossible without deployment-specific mappings.

### 5. Return bounded resource views, not document content

`POST /v1/clients` and `GET /v1/clients/{id}` return the client resource, source provenance, timestamps, and the governing authorization decision. `GET /v1/documents/{id}` returns title, source, nullable client identity, current version and indexing status, plus ingestion and retrieval authorization identities; it does not return version content.

All gets query by `(tenant_id, resource_id)` after membership authorization. Unknown and cross-tenant identities therefore produce the same `404`. The current version is derived deterministically as the highest version number, matching current search semantics, and its indexing job supplies status.

### 6. Extend existing authorization and audit patterns

Add narrow action values for client create/read, client-scoped document ingest, and document read. Reuse the current identity-to-membership authorization service. Application transactions append outcome events with IDs, reason categories, and request correlation only; email, names, descriptions, links, content, idempotency keys, bearer tokens, and raw claims never enter audit metadata or logs.

Authorization is evaluated before resource lookup. Allowed lookup decisions are retained even when a resource returns `404`, making the absence outcome auditable without leaking it to unauthorized callers.

## Risks / Trade-offs

- [Application-only requirement for new `documents.client_id`] → Keep the column nullable solely for migration compatibility, centralize all writes in the ingestion service, test direct API invariants, and schedule a later constraint only after real backfill evidence exists.
- [Concurrent email or idempotency races surface database integrity errors] → Use named unique constraints, transaction rollback, safe re-read where appropriate, and deterministic `409` or replay responses.
- [Email case folding differs from full mailbox-provider semantics] → Define uniqueness as trimmed lowercase equality only; do not alter dots, plus tags, or provider-specific mailbox syntax.
- [Breaking removal of `POST /v1/documents`] → Update OpenAPI, examples, tests, and runbook together; the platform is pre-release and the nested route establishes the intended product invariant.
- [JSON social links could grow or contain unsafe schemes] → Validate count, item length, and HTTP(S) scheme at the API/domain boundary and cap serialized size.
- [Client PII expands breach and observability exposure] → Keep responses authorization-scoped, audit only opaque IDs/categories, and add explicit log-capture tests for client fields.

## Migration Plan

1. Add the `clients` and `client_creation_requests` tables, including named tenant-scoped uniqueness constraints and indexes.
2. Add nullable `documents.client_id` with a foreign key and tenant-leading lookup index; leave existing rows null.
3. Deploy application code that requires the nested client path for every new ingestion and can read legacy null associations.
4. Verify migration upgrade/downgrade, legacy search preservation, tenant isolation, idempotency races, and API contracts before release.
5. Roll back application code first if necessary, then downgrade the migration only after confirming no new client-associated records must be retained; otherwise restore forward and correct the application.
