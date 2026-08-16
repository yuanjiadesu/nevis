## Context

The platform already persists tenant-owned documents, immutable versions, deterministic chunks, 384-dimensional vectors, embedding-profile identities, advisor memberships, and immutable authorization decisions. Protected ingestion establishes the trusted-gateway principal convention, and the repository layer exposes a tenant predicate intended to be composed before future ranking. See [proposal.md](proposal.md) for motivation and [document-search/spec.md](specs/document-search/spec.md) for observable behavior.

Search spans the API, authorization application service, PostgreSQL retrieval queries, the embedding runtime, audit persistence, migrations, and operational telemetry. The principal design constraint is that tenant isolation is part of candidate selection rather than response filtering.

## Goals / Non-Goals

**Goals:**

- Keep authorization evaluation and tenant scoping ahead of every retrieval branch.
- Produce useful, deterministic document-level ordering from lexical and semantic chunk evidence.
- Preserve two distinct authorization lineages: the decision that permitted indexing and the decision that permits this retrieval.
- Keep search available in an explicit lexical degradation mode when TEI is unavailable.
- Establish measurable relevance, isolation, latency, and audit contracts suitable for production iteration.

**Non-Goals:**

- Client/advisor entity search or a mixed client-and-document result list.
- Generative answers, reranking models, conversational memory, LangChain/LangGraph, or agent execution.
- File extraction, OCR, object storage, or ingestion changes.
- Cross-tenant administrative search, configurable sharing policies, or per-document ACLs.
- Reindex orchestration when changing embedding profiles; existing profile lineage remains authoritative.

## Decisions

### 1. Protected API and application boundary

Add `GET /search?q=<text>&limit=<n>&cursor=<opaque>` under the existing trusted-gateway dependency. Authorization evaluates a new `document.search` action and persists its decision before retrieval. The application service receives only an allowed authorization context; denied requests never call retrieval repositories.

The response contains `mode`, `results`, and `next_cursor`. Each document result contains title, a bounded supporting snippet, fused and component scores, and provenance identifiers for tenant, source, document, version, embedding profile, originating indexing decision, and current search decision.

Alternative considered: accept tenant/advisor identifiers directly in the search service. Rejected because it would duplicate the gateway and authorization boundary already used by protected ingestion.

### 2. Tenant-restricted candidate relations

Lexical and semantic retrieval start from a shared authorized relation joining current successfully indexed document versions to chunks and applying tenant ID, active embedding profile, and authorization-result predicates. Candidate CTEs consume that relation; tenant filtering is never applied after ranking or document aggregation.

The initial implementation uses exact cosine distance within the authorized bounded relation, prioritizing isolation and deterministic correctness. Add a B-tree index on `(tenant_id, embedding_profile_id, document_version_id)` and a GIN full-text index. Capture query plans and latency at realistic fixture sizes before introducing approximate ANN. If exact retrieval breaches the latency objective, a later change can introduce tenant-pruned partitioning or filtered ANN without changing the API contract.

Alternative considered: a global HNSW index followed by tenant filtering. Rejected for this slice because approximate traversal over a global corpus can under-return tenant candidates and makes the "filter before ranking" invariant harder to demonstrate.

### 3. Lexical representation and semantic profile

A migration adds separate stored PostgreSQL `tsvector` representations for chunk content and document title using the English text-search configuration, plus GIN indexes for each. Lexical retrieval uses `websearch_to_tsquery`, combines title and chunk evidence within the authorized relation, ranks with `ts_rank_cd`, and selects a bounded top-candidate set.

The query is embedded once through the provider-neutral runtime. Semantic candidates must match the exact active embedding-profile ID used for that query, use cosine similarity, and satisfy a configurable minimum similarity. A provider error switches only the semantic branch off and records `lexical_degraded`; it never substitutes vectors from another profile.

Alternative considered: application-side token matching or a second search service. Rejected because PostgreSQL already owns transactional document state, full-text search, vectors, and tenant predicates at the expected initial scale.

### 4. Deterministic fusion and document aggregation

Each branch emits at most a configured candidate count. Reciprocal-rank fusion combines lexical and semantic ranks with a versioned constant; a branch missing a document contributes zero. Results aggregate by document/version, retain the highest-ranked supporting chunk, and order by fused score descending then document UUID ascending.

Thresholds, candidate counts, rank-fusion version, and snippet bounds live in typed settings and are captured in safe telemetry. They are not silently changed: relevance fixtures make ranking changes reviewable.

Alternative considered: normalize and add raw lexical and cosine scores. Rejected because their scales are unrelated and sensitive to corpus/model changes; rank fusion is more stable for the first calibrated implementation.

### 5. Signed keyset cursor

The cursor is a versioned, URL-safe, HMAC-signed payload containing a query fingerprint, tenant ID, embedding-profile ID, retrieval mode, final fused score, final document ID, and issuance time. The signing key is required outside development/test. Cursor verification occurs before retrieval, followed by authorization; cursor contents are never trusted as the source of tenant identity.

Pagination uses the total ordering `(fused_score DESC, document_id ASC)`. Cursors have a bounded lifetime. Because the search is not a snapshot, concurrent indexing can shift later pages; that limitation is documented.

Alternative considered: offset pagination. Rejected because it becomes increasingly expensive and unstable as result sets grow.

### 6. Audit and telemetry boundaries

The authorization evaluator emits its existing allow/deny event. A successful search additionally appends `document.search.completed`, referencing the search decision and recording only: SHA-256 query fingerprint, retrieval mode, result document/version IDs, bounded rounded scores, count, duration, embedding-profile ID, and degradation code. No raw query, snippet, chunk content, vector, email, or credential is logged or placed in tracing attributes.

The audit write participates in the search request's database transaction. If it cannot be persisted, the request fails rather than returning an unaudited result. Operational metrics use low-cardinality mode/outcome labels; tenant and document IDs remain structured audit data rather than metric labels.

### 7. Failure behavior

Embedding unavailability is the only degraded-success path. Authorization failure, database failure, invalid cursor, and audit-persistence failure return no partial results. Safe error classes map to stable HTTP responses without dependency addresses, SQL, credentials, query text, or cross-tenant existence signals.

## Risks / Trade-offs

- [Exact semantic ranking may become slow for very large tenants] → Bound authorized candidates by active profile, add supporting indexes, capture `EXPLAIN` plans and p95 latency, and gate any ANN redesign on measured data.
- [RRF and thresholds can produce weak relevance] → Add labelled lexical/semantic/hybrid fixtures and version ranking parameters.
- [Lexical degradation changes ordering and invalidates a hybrid cursor] → Bind cursors to retrieval mode and reject mismatches rather than mixing modes across pages.
- [Concurrent indexing changes pagination] → Use deterministic keyset ordering, document the non-snapshot contract, and consider snapshot tokens only if product usage requires them.
- [Returning provenance identifiers expands the public contract] → Expose identifiers only after authorization and keep raw content and internal decision context out of responses.
- [A search audit can grow quickly] → Store bounded result metadata, index audit lookup fields, and establish retention/archival separately without allowing application mutation.

## Migration Plan

1. Add full-text representation and supporting tenant/profile/search indexes using an Alembic migration; backfill existing chunks transactionally or in bounded batches according to measured corpus size.
2. Deploy query models, cursor signing configuration, repository queries, search service, and protected endpoint while keeping the route disabled until migration completion.
3. Run cross-tenant, ranking, failure-mode, migration upgrade/downgrade, and Compose tests against indexed fixtures.
4. Enable the route and monitor mode distribution, empty-result rate, dependency degradation, and p50/p95 latency.
5. Roll back by disabling the route and reverting application code; retain additive search indexes during emergency rollback, then remove them with the migration downgrade during a controlled maintenance operation.

## Open Questions

- Final lexical and semantic thresholds will be calibrated from the first labelled wealth-management fixture set; changing their values does not alter the external contract.
