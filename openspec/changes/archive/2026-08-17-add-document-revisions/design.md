## Context

The ingestion service already created a new version when changed content reused a source and external ID. The console always generated a new external ID, while the safe document resource omitted content.

## Goals / Non-Goals

**Goals:**

- Add tenant-authorised editing for client documents
- Preserve document, source, idempotency, version, and indexing behavior
- Keep the general document resource content-free

**Non-Goals:**

- File upload or collaborative editing
- Restoring or deleting versions
- Changing document-client association

## Decisions

### Add edit and revision routes

`GET /v1/documents/{document_id}/edit` returns editable current content. `POST /v1/documents/{document_id}/revisions` creates a revision.

The server resolves source, external ID, and client before reusing the ingestion path. The browser cannot choose stable document identity.

### Authorise content reads explicitly

The normal resource stays metadata-only. The edit route makes content access intentional, tenant-authorised, and auditable.

### Preserve identity and immutable versions

The revision request does not accept client or external ID. Changed normalized content creates the next version. Unchanged content replays the current version. Documents without a client cannot use the console edit flow.

## Risks / Trade-offs

- **Content exposure**: Authorise before retrieval, return generic `404`, and audit without content
- **Concurrent revisions**: Create sequential immutable versions and expose the edited base version
- **Title changes**: Keep current title on the document and display the latest submitted title

## Migration Plan

1. Add edit and revision contracts with tests
2. Add the console edit flow and refresh timelines after acceptance
3. Hide the edit action to roll back

Existing versions and ingestion records remain valid after rollback.
