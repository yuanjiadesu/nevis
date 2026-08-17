## Why

Concurrent submissions can read the same document state before either commits. This can turn a valid replay or revision into a database conflict and expose a `500` response.

## What Changes

- Serialize ingestion for the same tenant and logical document
- Recheck idempotency after serialization
- Return replay, accepted, or `409` outcomes for concurrent submissions
- Add database-backed concurrency tests

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `document-ingestion`: Define deterministic outcomes for concurrent document submissions

## Impact

The change affects document ingestion transactions, PostgreSQL repository helpers, HTTP conflict handling, and integration tests. It adds no migration or dependency.
