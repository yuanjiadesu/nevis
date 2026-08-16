## 1. Tenant and authorization persistence

- [x] 1.1 Add tenant, advisor, advisor-membership, and immutable authorization-decision models with appropriate tenant/membership uniqueness constraints.
- [x] 1.2 Create an Alembic migration that preserves organization UUIDs while converting bootstrap ownership to `nevis-global` tenant ownership and rebuilding affected constraints.
- [x] 1.3 Backfill an explicit immutable migration decision for existing document versions, indexing jobs, and chunks while preserving existing audit-event history.
- [x] 1.4 Add repositories for tenant/advisor lookup, active-membership resolution, authorization-decision persistence, and tenant-scoped document queries.

## 2. Authorization domain and application boundary

- [x] 2.1 Define authorization context, action identifiers, allow/deny outcomes, and a versioned active-membership policy in the domain layer.
- [x] 2.2 Implement authorization evaluation that records credential-safe immutable decisions and append-only audit events for allowed and denied protected actions.
- [x] 2.3 Add a reusable tenant authorization predicate for protected document records, designed to compose into pre-ranking retrieval queries.
- [x] 2.4 Update ingestion and document-version status application services to accept authorization context, scope all persistence/lookups to a tenant, and retain the decision reference in provenance.

## 3. Protected API surface and bootstrap operation

- [x] 3.1 Add the trusted-gateway principal adapter and documented development/test headers for tenant and advisor assertions; reject missing or invalid protected contexts.
- [x] 3.2 Apply the authorization dependency to document ingestion and document-version status endpoints, returning non-disclosing responses for unauthorized version access.
- [x] 3.3 Provide an operator-controlled bootstrap/provisioning path for the initial `nevis-global` advisor membership without adding tenant-management endpoints.
- [x] 3.4 Update OpenAPI descriptions, README, and runbook with the gateway trust boundary, authorization headers, provisioning procedure, and changed manual test flow.

## 4. Indexing lineage propagation

- [x] 4.1 Update indexing job and chunk persistence to retain tenant and authorization-decision references rather than only global policy/result fields.
- [x] 4.2 Ensure retry, failure, and interrupted-work paths preserve the originating ingestion authorization decision and tenant provenance.
- [x] 4.3 Add internal inspection assertions that every persisted retrievable chunk is attributable to tenant, source, document version, embedding profile, and authorization decision.

## 5. Verification and delivery checks

- [x] 5.1 Add unit tests for membership authorization, allow/deny decision/audit emission, and pre-retrieval tenant predicates.
- [x] 5.2 Add API integration tests for authorized ingestion/status, missing or inactive membership, cross-tenant status non-disclosure, and tenant-local idempotency.
- [x] 5.3 Add worker and migration integration tests proving existing corpus backfill, two-tenant indexing isolation, decision provenance, and recovery behavior.
- [x] 5.4 Run formatting, linting, type checks, unit/integration tests, migration upgrade/downgrade checks, Compose smoke checks, and strict OpenSpec validation.
