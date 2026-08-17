## MODIFIED Requirements

### Requirement: Keep document ownership stable

The system SHALL bind every document to exactly one same-tenant client. It SHALL reject documents without clients and include client identity in idempotency fingerprints and provenance.

#### Scenario: Existing document uses another client

- **WHEN** a source and external ID identify a document owned by another same-tenant client
- **THEN** the system returns `409` without changing association, creating a version, or queuing indexing

#### Scenario: Idempotency key uses another client

- **WHEN** an idempotency key is reused with a different client
- **THEN** the system reports a conflict and changes no document record

#### Scenario: Adviser revises a document

- **WHEN** an adviser creates a version of an existing document
- **THEN** the system reuses its client without requiring it in the request

## REMOVED Requirements

### Requirement: Preserved legacy document lineage
