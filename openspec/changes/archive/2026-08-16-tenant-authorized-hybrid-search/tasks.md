## 1. Search schema and configuration

- [x] 1.1 Add typed search settings for query/limit bounds, branch candidate counts, semantic threshold, RRF version and constant, snippet length, cursor TTL, and environment-aware cursor signing key validation.
- [x] 1.2 Extend document and chunk models with stored English full-text vectors and tenant/profile retrieval indexes without changing existing lineage identities.
- [x] 1.3 Add an Alembic migration and downgrade for document-title and chunk-content full-text vectors and indexes, including backfill behavior for the existing corpus.
- [x] 1.4 Add migration integration checks for upgrade/downgrade, vector backfill, GIN indexes, and preservation of tenant, document-version, embedding-profile, and authorization-decision references.

## 2. Search domain and cursor contract

- [x] 2.1 Define search query, retrieval mode, component score, result, provenance, page, and credential-safe failure types independent of FastAPI and SQLAlchemy.
- [x] 2.2 Add the `document.search` authorization action and ensure allowed and denied decisions use the existing immutable decision/audit boundary.
- [x] 2.3 Implement versioned HMAC-signed keyset cursor encoding and validation bound to query fingerprint, tenant, embedding profile, retrieval mode, score, document identity, and expiry.
- [x] 2.4 Add unit tests for query normalization and bounds, deterministic ordering, cursor round-trip/tamper/expiry/context mismatch, and safe error classification.

## 3. Tenant-scoped retrieval and ranking

- [x] 3.1 Implement a shared authorized current-version chunk relation that applies tenant, allowed-decision, successful-indexing, and active-profile predicates before candidate ordering or projection.
- [x] 3.2 Implement bounded lexical document/chunk retrieval with PostgreSQL full-text ranking and safe supporting-snippet selection.
- [x] 3.3 Implement bounded exact cosine retrieval using only vectors for the query's active embedding profile and enforcing the configured semantic threshold.
- [x] 3.4 Implement versioned reciprocal-rank fusion, current-version document aggregation, best-supporting-chunk selection, deterministic tie-breaking, and keyset continuation.
- [x] 3.5 Add repository integration tests proving cross-tenant candidates cannot affect scores, order, count, pagination, or provenance; historical and incompletely indexed versions remain excluded.

## 4. Search application service and API

- [x] 4.1 Implement the search application service to authorize first, resolve one active embedding profile, execute hybrid retrieval, and return lexical degradation only for embedding-runtime unavailability.
- [x] 4.2 Persist `document.search.completed` audit events with query fingerprint, result/version identities, bounded rounded scores, mode, latency, profile, and decision references while excluding customer content and credentials.
- [x] 4.3 Add the protected `GET /search` endpoint, request/response models, OpenAPI descriptions, trusted-gateway headers, stable validation errors, and credential-safe dependency failures.
- [x] 4.4 Add API tests for hybrid, lexical-degraded, empty, invalid-query, invalid-cursor, missing/inactive membership, cross-tenant non-disclosure, and audit-write failure behavior.
- [x] 4.5 Add a real-TEI Compose smoke path that ingests and indexes fixtures, searches as a provisioned advisor, validates result provenance, and proves a second tenant remains invisible.

## 5. Relevance, performance, and observability

- [x] 5.1 Create labelled wealth-management search fixtures covering exact terms, paraphrases, weak/nonsense queries, multiple chunks, version replacement, and lexical-versus-semantic complementarity.
- [x] 5.2 Add deterministic relevance regression tests for lexical, semantic, hybrid, threshold, fusion, aggregation, and pagination behavior using the fake embedding provider where appropriate.
- [x] 5.3 Add safe structured telemetry for latency, candidate/result counts, retrieval mode, outcome, and degradation code with tests proving raw query/content, email, vector, decision context, and provider credentials are excluded.
- [x] 5.4 Capture PostgreSQL query plans at representative fixture scale, document the exact-search performance baseline, and enforce a measured p95 search target in a repeatable benchmark command.

## 6. Documentation and delivery validation

- [x] 6.1 Update README and the operational runbook with the search contract, gateway headers, cursor behavior, lexical degradation, safe troubleshooting, and local fixture flow.
- [x] 6.2 Update CI to run search unit/integration/relevance tests, migration validation, and the authorized real-TEI Compose smoke scenario.
- [x] 6.3 Run formatting, linting, type checks, full tests, migration upgrade/downgrade checks on an isolated database, Compose smoke checks, and strict OpenSpec validation.
- [x] 6.4 Confirm the implementation adds document retrieval only and does not introduce client search, generative answers, file extraction, cross-tenant administration, or an agent framework.
