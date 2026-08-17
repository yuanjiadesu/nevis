## Why

Documents could remain without a client because `client_id` was introduced as nullable. Those records appeared as legacy search results that advisers could not open. The product rule is stricter: every document belongs to one client.

## What Changes

- **BREAKING:** Require `documents.client_id`
- Delete documents without clients and their versions, chunks, jobs, and ingestion requests
- Return client identity and display name on every document result
- Remove revision and console paths for unassociated documents

## Capabilities

### Modified Capabilities

- `document-ingestion`: Require client association
- `document-search`: Include client identity and display name on document results

## Impact

The migration irreversibly deletes unowned documents because no correct client can be inferred. It makes `client_id` required in document responses and search provenance, and adds `client_name` to document results.

The change also affects search queries, domain models, revisions, generated console types, and result presentation.
