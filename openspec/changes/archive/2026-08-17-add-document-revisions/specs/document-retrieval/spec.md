## MODIFIED Requirements

### Requirement: Return current document state and lineage

The safe document resource SHALL return document identity, title, source, client association when present, current version, indexing state, tenant, ingestion decision, and retrieval decision without content. Only the authorised edit representation SHALL return current plain-text content.

#### Scenario: Return an associated document

- **WHEN** an authorised adviser retrieves a client-scoped document
- **THEN** the safe resource returns lineage and current state without content

#### Scenario: Return editable content

- **WHEN** an authorised adviser requests a client-scoped document’s edit representation
- **THEN** it returns current plain-text content and current version identity

#### Scenario: Return a legacy document

- **WHEN** an authorised adviser retrieves a document created before mandatory client association
- **THEN** the resource reports no client and preserves tenant and ingestion lineage
