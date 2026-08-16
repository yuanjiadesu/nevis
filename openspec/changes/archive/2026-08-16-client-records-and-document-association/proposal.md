## Why

The platform can ingest and search tenant-owned documents, but it cannot yet represent the clients those documents belong to. Adding the client boundary now completes the core ownership model needed before client matching and mixed client/document search can be designed safely.

## What Changes

- Add tenant-owned client creation and retrieval with normalized, case-insensitively unique email addresses.
- Require authenticated advisor membership before client or document lookup, and retain authorization decisions and credential-safe audit events for each outcome.
- **BREAKING** Replace unscoped `POST /v1/documents` ingestion with `POST /v1/clients/{client_id}/documents`, requiring an existing same-tenant client while reusing the existing immutable versioning and durable indexing pipeline.
- Add retrieval of a document resource and its current indexing state without exposing content or existence across tenant boundaries.
- Add idempotency and deterministic conflict behavior for client creation.
- Keep client search and mixed client/document ranking out of this change.

## Capabilities

### New Capabilities

- `client-records`: Tenant-authorized creation and retrieval of client records, including tenant-scoped case-insensitive email uniqueness, idempotency, auditability, and safe provenance.
- `document-retrieval`: Tenant-authorized retrieval of a document resource, its client association, current version, and indexing state.

### Modified Capabilities

- `document-ingestion`: Require an existing same-tenant client association when accepting a document while preserving the current immutable, idempotent indexing flow.
- `tenant-advisor-authorization`: Extend the existing authorization boundary and pre-retrieval predicate from document-only actions to client and document resources.

## Impact

- Adds a client persistence model, tenant-scoped constraints and indexes, and document-to-client ownership through an Alembic migration.
- Adds client create/get and document get HTTP contracts, and extends document ingestion without changing the worker or embedding-provider contracts.
- Extends application services, repositories, authorization actions, audit events, API documentation, fixtures, and unit/integration/contract/E2E coverage.
- Existing document rows require a staged migration strategy: preserve them as explicitly unassociated legacy records while requiring a client for every new ingestion.
