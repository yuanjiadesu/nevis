## Why

Nevis missed the required `address proof` to `utility bill` match. The embedding ranked an address-change negative above the evidence, so one vector threshold could not fix the result. Previews also showed chunk openings instead of supporting passages.

## What Changes

- Route complete emails and domains to literal retrieval
- Add punctuation-aware email and token-prefix identity and title matching
- Keep document content on whole-term lexical matching
- Retrieve lexical and vector candidates before reranking document passages
- Return the winning source passage as the preview
- Select a pinned local reranker through seeded quality and CPU gates
- Publish the complete policy as `mixed-rrf-v3`

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `document-search`: Field-specific matching, routing, hybrid recall, evidence ranking, degraded modes, and source previews

## Impact

Changed search orchestration, candidate retrieval, ranking, previews, cursors, audit metadata, seed data, evaluation fixtures, and documentation. PostgreSQL and pgvector remained the search store. No document migration was required.
