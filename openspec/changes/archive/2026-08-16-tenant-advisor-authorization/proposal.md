## Why

The current `nevis-global` authorization decision is intentionally permissive and cannot protect one advisory firm's data from another's. Before semantic retrieval is introduced, the platform needs a tenant and advisor authorization boundary that is enforceable, auditable, and compatible with the provenance already captured during ingestion and indexing.

## What Changes

- Introduce tenants, advisors, and tenant memberships as the platform's access-control domain.
- **BREAKING** Make `nevis-global` the initial tenant and migrate existing document lineage and audit ownership to tenant-scoped records.
- Require an explicit authorization context and durable allow/deny decision for tenant-scoped document ingestion and document-version status access.
- Define the reusable authorization predicate that future retrieval must apply before vector ranking; this change does not add a search endpoint.
- Preserve every document version and embedded chunk's attribution to its tenant, source, document version, embedding profile, and authorization decision.

## Capabilities

### New Capabilities

- `tenant-advisor-authorization`: Tenant, advisor-membership, authorization-decision, and pre-retrieval filtering behavior.

### Modified Capabilities

- `global-data-lineage`: Replace the global-only ownership and allow decision baseline with the initial `nevis-global` tenant and tenant-aware audit lineage.
- `document-ingestion`: Make document ingestion, idempotency, provenance, and audit decisions tenant-scoped.
- `document-indexing`: Retain tenant authorization context for indexed chunks and vectors so future retrieval can be filtered before ranking.

## Impact

- Database schema and migration/backfill for tenant and advisor identities, memberships, authorization decisions, and existing ownership records.
- FastAPI request context and authorization dependency for ingestion and document-version status APIs.
- Domain/application authorization service, repositories, audit events, worker provenance, test fixtures, and operational documentation.
- No new external identity provider, semantic-search API, or LLM capability in this change.
