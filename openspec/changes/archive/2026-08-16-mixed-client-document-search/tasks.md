## 1. Client search persistence and domain foundation

- [x] 1.1 Add typed client/document candidate and result variants, match bands, branch-rank metadata, `mixed-rrf-v1` identity, and a common deterministic ordering key to the search domain.
- [x] 1.2 Extend client persistence with a generated English search vector and tenant-leading normalized full-name/general-search indexes while preserving existing client identities and uniqueness.
- [x] 1.3 Add an Alembic upgrade/downgrade migration for the client search vector and indexes, including migration-chain and schema-drift coverage.
- [x] 1.4 Add bounded settings for client candidate count, mixed branch weights, ranking version, and client description excerpt length with safe production defaults and validation.

## 2. Authorized client candidate retrieval

- [x] 2.1 Add tenant-predicated exact normalized-email retrieval that returns only bounded client search fields and creation-decision lineage.
- [x] 2.2 Add tenant-predicated exact normalized full-name retrieval with deterministic client-ID ordering.
- [x] 2.3 Add tenant-predicated PostgreSQL full-text client retrieval across names and description with thresholding, bounded candidates, stable ranking, and no cross-tenant fallback query.
- [x] 2.4 Add query-plan and representative-volume tests proving the exact and general client branches use the intended tenant-leading indexes.

## 3. Mixed ranking and pagination

- [x] 3.1 Refactor existing document fusion to expose document lexical and semantic branch ranks without changing current-version, active-profile, threshold, or aggregation behavior.
- [x] 3.2 Implement `mixed-rrf-v1` exact-email/full-name precedence and weighted rank fusion across client lexical, document lexical, and document semantic branches without comparing raw scores.
- [x] 3.3 Apply the total deterministic key of match band, fused score, result type, and stable UUID, including duplicate suppression and type-appropriate provenance construction.
- [x] 3.4 Version the signed cursor payload with ranking version, match band, result type, result UUID, and existing query/tenant/profile/mode bindings; reject legacy or context-mismatched cursors safely.
- [x] 3.5 Preserve mixed client/document results in `lexical_degraded` mode using client and document lexical branches when query embedding is unavailable.

## 4. Application, HTTP, audit, and telemetry contracts

- [x] 4.1 Replace the document-search authorization action with a narrow mixed-search action while retaining one committed allow/deny decision before every client or document lookup.
- [x] 4.2 Extend the search application service to obtain one active profile and query embedding, execute all authorized branches, rank once, paginate once, and return one mixed page.
- [x] 4.3 Replace the `/search` response with a discriminated client/document union in FastAPI and OpenAPI, including bounded type-specific fields, component metadata, and provenance.
- [x] 4.4 Replace document-only search audit data with typed opaque result identities, ranking version, type counts, bounded rank metadata, mode, profile, duration, and degradation code.
- [x] 4.5 Update telemetry allowlists and add log/audit assertions proving query text, client email/name/description, snippets, content, vectors, cursors, and credentials are never emitted.

## 5. Verification and evaluation

- [x] 5.1 Add unit tests for client query normalization, match-band precedence, weighted fusion, type tie-breakers, duplicate suppression, degraded ranking, and mixed cursor boundaries.
- [x] 5.2 Add PostgreSQL integration tests for exact email/name and general client retrieval, same-match cross-tenant exclusion, thresholds, indexes, and deterministic branch order.
- [x] 5.3 Add HTTP contract tests for both discriminated result variants, mixed ordering, exact-client precedence, validation, authorization failures, cursor rejection, and production OIDC identity precedence.
- [x] 5.4 Extend E2E fixtures to create multiple clients/documents, index through the existing worker, return a genuinely mixed list, preserve legacy unassociated document provenance, and prove cross-tenant isolation.
- [x] 5.5 Extend labelled relevance fixtures and metrics with exact email/name, description, document semantic, ambiguous mixed, and nonsense queries; record Recall@k/MRR and ranking-version evidence.
- [x] 5.6 Extend the performance harness to representative client/document volume and verify tenant-first query plans plus the master plan's indexed-search p95 objective.
- [x] 5.7 Run Ruff formatting/linting, mypy, the full pytest suite, Alembic downgrade/upgrade/check, strict OpenSpec validation, Compose configuration validation, and the real-TEI mixed-search smoke path.

## 6. Documentation and handoff

- [x] 6.1 Update README and API documentation with the breaking discriminated response, exact client precedence, mixed examples, cursor invalidation, and degraded behavior.
- [x] 6.2 Update architecture and runbook documentation with client indexes, `mixed-rrf-v1`, PII-safe operations, relevance/performance verification, rollout, and rollback.
- [x] 6.3 Update the master plan only after verification proves mixed search complete, and leave fuzzy/client-semantic search and learned ranking as evidence-driven future options.
