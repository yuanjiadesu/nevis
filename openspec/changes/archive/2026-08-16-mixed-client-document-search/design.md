## Context

The current `/search` path authorizes tenant membership before retrieving current document chunks, obtains lexical and semantic document ranks, fuses them with reciprocal-rank fusion, and returns document-only results with signed pagination. Client records now have tenant ownership, normalized unique email, bounded names/description, creation-decision lineage, and tenant-scoped reads. See `proposal.md` for the product motivation and the two delta specs for observable behavior.

The declared envelope is approximately 10,000 clients with 10–100 documents per client. The design should deepen the existing FastAPI/PostgreSQL modular monolith, preserve the provider-neutral document embedding contract, and avoid a second search service or client indexing worker.

## Goals / Non-Goals

**Goals:**

- Produce one deterministic, paginated client/document list whose branches are tenant-filtered before ranking.
- Give exact client email/name lookups predictable precedence without letting incomparable raw scores define cross-type order.
- Preserve current document hybrid retrieval, lexical degradation, provenance, audit safety, and performance targets.
- Keep the result and cursor model evolvable through explicit ranking/schema versions.

**Non-Goals:**

- Client embeddings, typo-tolerant matching, maintained synonyms, LLM rewriting, recency/personalization boosts, advisor-specific ownership, or a second endpoint.
- Changing document chunking, embedding profiles, indexing jobs, or worker behavior.
- Returning full client descriptions or document content from search.

## Decisions

### 1. Add PostgreSQL lexical client retrieval, not client embeddings

Add a generated English full-text vector over client names and description with a tenant-leading GIN-supported retrieval path. Use the existing `(tenant_id, normalized_email)` uniqueness index for exact email and a tenant-leading normalized full-name expression index for exact name. General client retrieval uses bounded PostgreSQL full-text ranking and returns only tenant-scoped candidates.

This gives exact identity behavior and useful description search at the stated 10k-client scale without creating a second embedding lifecycle or placing client PII in the embedding provider. Client embeddings were rejected because they add versioning, re-indexing, deletion/privacy, profile migration, and provider-exposure concerns without a stated semantic-client-search requirement. Trigram/fuzzy matching remains a later evidence-driven option.

### 2. Use precedence bands plus versioned weighted rank fusion

Represent every candidate with a typed identity, match band, branch ranks, and common fused score. The initial `mixed-rrf-v1` policy orders:

1. exact normalized client email;
2. exact case-insensitive client full name;
3. general candidates fused from client lexical, document lexical, and document semantic ranks.

Within the general band, apply weighted reciprocal-rank fusion to branch positions, not raw branch scores. Keep initial weights explicit configuration constants covered by labelled relevance tests; use stable result-type then UUID tie-breakers. This protects exact lookup intent while allowing clients and documents to interleave for general queries.

Raw-score normalization was rejected because PostgreSQL text rank and cosine similarity have unrelated, corpus-sensitive distributions. Concatenating independently sorted lists was rejected because it permanently privileges a type rather than evidence. A learned ranker is unjustified without production labels.

### 3. Replace the response with a discriminated union

Keep `GET /search` but return `results` containing `type: client` or `type: document`.

- Common fields: `type`, display title, bounded excerpt/snippet, common rank score, component/rank metadata, and search authorization decision.
- Client fields/provenance: client ID, bounded email/display fields, tenant ID, creation decision.
- Document fields/provenance: nullable client ID, source/document/current-version/profile IDs, indexing decision, tenant ID.

Do not preserve the document-only shape because that creates an ambiguous transitional contract. FastAPI OpenAPI uses the discriminator, and contract tests prove both variants. This is an intentional pre-release breaking change.

### 4. Version and sign the mixed cursor context

Replace the document-only cursor position with `ranking_version`, match band, fused score, result type, and result UUID while retaining query fingerprint, tenant, active profile, retrieval mode, issue time, expiry, and signature. Pagination filters the fully ranked mixed relation after deterministic ordering.

Old cursors fail as generic invalid cursors rather than being translated. Cursor versioning avoids silently applying obsolete ordering after ranking changes.

### 5. Preserve one authorization decision and one query embedding

Use a narrow mixed-search authorization action. After the allow decision is committed, execute each repository branch with the authorized tenant predicate; no branch accepts a caller-provided tenant independently. Obtain the active profile and query embedding once, exactly as today. If embedding fails, execute client and document lexical branches and report `lexical_degraded`.

This keeps a single causal authorization decision across all result types and avoids duplicate provider calls. A separate client search endpoint/action was rejected because the required product contract is one list and split decisions complicate audit attribution.

### 6. Audit typed identities and ranking evidence without customer text

Record query fingerprint, ranking version, retrieval mode, candidate/result counts by type, typed opaque result IDs, bounded fused/component ranks, active profile, duration, and degradation code. Never record query text, client names/emails/descriptions, snippets, content, vectors, cursor contents, or provider credentials. Keep metrics low-cardinality and type-aggregated.

## Risks / Trade-offs

- [Exact identity precedence can dominate a semantically strong document] → Limit precedence to exact normalized email/full-name matches and test representative ambiguous queries.
- [RRF weights encode product judgment] → Name the policy `mixed-rrf-v1`, keep constants centralized, publish labelled fixtures, and require a new version for behavior-changing calibration.
- [English FTS is weak for typos or non-English names] → Make exact matching case-insensitive, document the English-only envelope, and add trigram or locale-aware search only with measured need.
- [Mixed pagination can duplicate/skip records if data changes between pages] → Preserve the existing cursor semantics and deterministic boundary; snapshot pagination is out of scope and can be added if observed consistency requirements demand it.
- [Client PII could enter logs through new result handling] → Use explicit audit/telemetry allowlists and log-capture tests for email, name, description, and query exclusion.
- [A new generated vector/index increases write cost] → Measure client creation and search plans at representative scale; the client workload is read-heavy and the index remains PostgreSQL-local.

## Migration Plan

1. Add the client search vector and tenant-leading exact-name/general-search indexes without changing existing client identities.
2. Deploy repository branches and mixed domain/ranking code behind the new response contract; no dual-write or client backfill job is required because the generated vector derives from existing columns.
3. Deploy the API, cursor version, audit allowlist, evaluation fixtures, and documentation together as one pre-release breaking increment.
4. Verify tenant isolation, query plans, relevance thresholds, degraded mode, stable pagination, PII-safe operations, and p95 latency at representative volume before release.
5. Roll back the application first. The added generated column/indexes can remain safely during rollback; drop them later through the migration downgrade only when operationally appropriate.
