## MODIFIED Requirements

### Requirement: Return current document state and lineage

The safe document resource SHALL return document identity, title, source, client association, tenant, current version, indexing status, authorization decisions, and `summary: string | null`. It SHALL return content only through the separately authorized edit representation.

#### Scenario: Return an associated document

- **WHEN** an authorized adviser retrieves a client-scoped document
- **THEN** the resource returns its lineage and current state without document content

#### Scenario: Return a ready summary

- **WHEN** the current version has a ready summary
- **THEN** the resource returns that bounded summary without document content

#### Scenario: Return an absent summary

- **WHEN** generation is disabled, pending, failed, or unsafe
- **THEN** the resource returns `summary: null`

#### Scenario: Return editable content

- **WHEN** an authorized adviser requests the edit representation
- **THEN** it returns the current plain-text content and version identity

#### Scenario: Return a legacy document

- **WHEN** an authorized adviser retrieves a document created before mandatory client association
- **THEN** the resource reports no client association and preserves existing tenant and ingestion lineage

### Requirement: Return a client document timeline

The system SHALL return a bounded, stable page of documents for an authorized same-tenant client. Each item SHALL include safe current-version state and `summary: string | null`. Summary availability SHALL NOT change membership, order, or pagination.

#### Scenario: Request an authorized timeline

- **WHEN** an active adviser requests a client’s document timeline in the explicit tenant
- **THEN** the system returns only that client’s documents, safe current state, nullable summaries, and an opaque next cursor when needed

#### Scenario: Mix summary states

- **WHEN** a timeline contains ready and absent summaries
- **THEN** all documents retain their existing order

#### Scenario: Request an absent or cross-tenant client

- **WHEN** an adviser requests an unknown or cross-tenant client
- **THEN** the system returns the same generic `404` response without document metadata
