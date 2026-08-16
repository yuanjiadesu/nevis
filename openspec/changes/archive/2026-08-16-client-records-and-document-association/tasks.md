## 1. Domain and persistence foundation

- [x] 1.1 Add client domain commands, results, validation, trimmed-lowercase email normalization, normalized request fingerprinting, and safe conflict/not-found errors.
- [x] 1.2 Add SQLAlchemy models for clients and client-creation idempotency records, including source provenance, creation authorization lineage, bounded social links, named uniqueness constraints, and tenant-leading indexes.
- [x] 1.3 Add nullable document-to-client persistence and update document domain/result types so new documents carry a client while legacy records can report no association.
- [x] 1.4 Create an Alembic upgrade/downgrade migration that preserves all existing document/version/chunk/embedding identities and search indexes while adding the client schema and nullable legacy association.

## 2. Client application capability

- [x] 2.1 Add tenant-scoped client repository operations for create, normalized-email conflict detection, idempotency lookup/recording, and retrieval without cross-tenant fallback queries.
- [x] 2.2 Implement transactional client creation with deterministic replay/conflict behavior, database-race handling, creation authorization lineage, and credential-safe created/replayed/conflicted audit events.
- [x] 2.3 Implement tenant-scoped client retrieval with a generic missing/cross-tenant outcome and credential-safe found/not-found audit events linked to the read authorization decision.

## 3. Client-associated document capability

- [x] 3.1 Extend ingestion commands, fingerprints, persistence, and results with the path client identity, resolving the same-tenant client before any ingestion state is created.
- [x] 3.2 Enforce immutable document-to-client association for new and updated documents, returning safe conflicts for reassignment or cross-client idempotency replays while preserving legacy unassociated rows.
- [x] 3.3 Add a tenant-scoped document resource query that derives the current version and indexing job and returns bounded source, client, status, ingestion-decision, and read-decision lineage without content.
- [x] 3.4 Add credential-safe document found/not-found audit events and confirm client PII, content, and idempotency keys cannot enter logs or audit metadata.

## 4. HTTP and authorization contracts

- [x] 4.1 Add bounded request/response schemas and routes for `POST /v1/clients` and `GET /v1/clients/{client_id}`, including idempotency, `409`, generic `404`, and existing `401`/`403` behavior.
- [x] 4.2 Replace `POST /v1/documents` with `POST /v1/clients/{client_id}/documents`, preserve its `202` indexing response, and map missing client and association conflicts without existence leakage.
- [x] 4.3 Add `GET /v1/documents/{document_id}` with current indexing state and complete bounded provenance while retaining the existing document-version status endpoint.
- [x] 4.4 Add narrow client-create, client-read, client-document-ingest, and document-read authorization actions and verify every resource lookup occurs only after membership authorization and with a tenant predicate.

## 5. Verification

- [x] 5.1 Add unit tests for client validation, email normalization, fingerprints, replay/conflict behavior, document association invariants, and PII-safe metadata.
- [x] 5.2 Add PostgreSQL integration tests for tenant-scoped email uniqueness, same-email cross-tenant behavior, idempotency and uniqueness races, tenant-filtered lookups, indexes/query plans, and migration upgrade/downgrade with legacy documents.
- [x] 5.3 Add HTTP contract tests for successful client/document workflows, validation and conflict responses, missing/cross-tenant indistinguishability, production identity precedence, OpenAPI schemas, and removal of unscoped ingestion.
- [x] 5.4 Add end-to-end coverage that creates a client, ingests and indexes its document, retrieves both resources with lineage, finds the document through existing search, and confirms a legacy unassociated document still works.
- [x] 5.5 Run Ruff formatting/linting, mypy, the full pytest suite, Alembic migration checks, strict OpenSpec validation, Docker Compose configuration validation, and the local TEI smoke path.

## 6. Documentation and handoff

- [x] 6.1 Update the README and API documentation with client fields, idempotency, nested ingestion examples, retrieval representations, error behavior, and the intentional breaking route change.
- [x] 6.2 Update architecture and runbook documentation with the client ownership relation, legacy-null migration behavior, PII-safe operations, rollback constraints, and manual verification commands.
- [x] 6.3 Update the master plan implementation status only after verification proves this increment complete, leaving mixed client/document search as the next bounded feature.
