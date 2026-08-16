## Why

The platform can ingest, authorize, chunk, and embed documents, but advisors cannot yet retrieve the indexed knowledge. The next production slice must expose useful document search while enforcing tenant isolation before candidate ranking and preserving enough lineage to explain every returned result.

## What Changes

- Add an authorized document-search API with validated queries, bounded page size, and deterministic cursor pagination.
- Retrieve tenant-scoped lexical and semantic chunk candidates in PostgreSQL, fuse their ranks, and aggregate supporting chunks into document results.
- Apply the existing active-membership authorization predicate before both lexical and vector ranking; denied and cross-tenant requests disclose no result data or counts.
- Return result provenance for tenant, source, document version, embedding profile, and the authorization decision governing the search.
- Persist a credential-safe search audit record containing result identities, ranking mode, timing, and the search authorization decision, without query text or document content.
- Degrade explicitly to lexical-only retrieval when the embedding runtime is unavailable; database or authorization failure remains fail-closed.
- Add relevance fixtures, tenant-isolation tests, query/ranking tests, and operational telemetry for search latency and retrieval mode.

## Capabilities

### New Capabilities

- `document-search`: Authorized tenant-scoped lexical and semantic document retrieval, rank fusion, pagination, result provenance, degradation behavior, and auditability.

### Modified Capabilities

None. The existing authorization, indexing, lineage, and embedding-runtime contracts already provide the boundaries consumed by search.

## Impact

- Adds a protected `GET /search` API and corresponding application search service.
- Adds PostgreSQL full-text retrieval indexes, pgvector similarity indexes, ranking queries, cursor state, and document-result aggregation.
- Extends audit emission and safe telemetry for search decisions, result identities, mode, and latency.
- Uses the existing embedding provider contract for query embeddings and the existing tenant/advisor gateway context.
- Does not introduce client-record search, file extraction, new hosted embedding dependencies, or an agent framework.
