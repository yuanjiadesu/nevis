## Why

Indexed documents can vanish from title search when a content-only reranker rejects them. Missing summaries also have no visible state or safe recovery path.

## What Changes

- Keep exact and prefix title matches even when document content fails reranking.
- Expose summary states: `not_requested`, `pending`, `processing`, `ready`, and `failed`.
- Add safe reconciliation for missing or failed fictional summary work.
- Detect API and worker summary-config drift.
- Add an end-to-end UAT check for indexing, title search, and summaries.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `document-search`: Preserve title matches independently of content reranking.
- `document-summarization`: Expose and reconcile summary work.
- `document-retrieval`: Return summary state with nullable summary text.
- `platform-runtime`: Detect summary-worker drift and verify delivery.

## Impact

Search retrieval and ranking, summary APIs and UI, worker diagnostics, deployment checks, generated clients, tests, and documentation change. Search storage, model providers, and authorization do not.
