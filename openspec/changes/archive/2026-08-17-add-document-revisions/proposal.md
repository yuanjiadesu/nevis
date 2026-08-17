## Why

The console created a new external document for every submission. Advisers could not revise one document or build meaningful version history.

## What Changes

- Add an authorised edit representation with current plain-text content
- Add a revision endpoint that creates the next immutable version
- Add an edit action that pre-fills title and content
- Preserve document identity, idempotency, indexing, tenant isolation, and lineage

## Capabilities

### New Capabilities

- `document-revision`: Authorised creation of successive immutable document versions

### Modified Capabilities

- `document-retrieval`: Purpose-specific access to editable current content

## Impact

Changed document routes, authorisation actions, audit events, ingestion services, OpenAPI types, console document actions, and API and browser tests.
