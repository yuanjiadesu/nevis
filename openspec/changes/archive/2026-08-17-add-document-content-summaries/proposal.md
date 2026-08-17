## Why

Document titles do not always explain their contents. A short summary helps advisers scan a client’s documents before opening them.

## What Changes

- Generate an optional two-sentence summary for each document version
- Process summaries after indexing, outside the ingestion request
- Return summaries from the document resource and client document timeline
- Label summaries as AI-generated and keep them out of search
- Call OpenCode Zen directly from the `mangabox` UAT environment for fictional test data

## Capabilities

### New Capabilities

- `document-summarization`: Generate a bounded summary for an immutable document version

### Modified Capabilities

- `document-retrieval`: Return the current version’s summary when available

## Impact

Add one `document_summaries` table, one configured OpenCode Chat Completions adapter, one test fake, and one lower-priority worker path. Provider identity, model, and endpoint are injected from validated deployment settings; `OPENCODE_API_KEY` remains the only provider secret.

Search, indexing, authorization, readiness, and pagination do not change. Existing versions remain unsummarized. Reseeding creates new versions through normal ingestion.
