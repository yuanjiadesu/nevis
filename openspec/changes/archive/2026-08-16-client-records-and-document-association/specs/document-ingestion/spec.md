## MODIFIED Requirements

### Requirement: Plain-text document ingestion
The system SHALL accept an authorized plain-text document submission through `POST /v1/clients/{client_id}/documents` containing a source reference, stable external document identifier, title, content, and idempotency key, and SHALL return the document-version identity and indexing status. The client SHALL exist in the explicitly requested tenant before a source, document, version, idempotency record, or indexing job is created.

#### Scenario: New document is accepted
- **WHEN** an authorized advisor submits a valid document for an existing same-tenant client with an unseen source and external document identifier
- **THEN** the system creates a source, client-associated document, first immutable document version, and queued indexing work under that tenant

#### Scenario: Document content is updated
- **WHEN** an authorized advisor submits different normalized content for an existing source and external document identifier through its associated client in the same tenant
- **THEN** the system creates a new immutable version and queues indexing only for that new version

#### Scenario: Client is missing or belongs to another tenant
- **WHEN** an authorized advisor submits a document for an unknown client identity or a client owned by another tenant
- **THEN** the system returns the same generic `404` response and creates no source, document, version, idempotency record, indexing job, or cross-tenant existence signal

## ADDED Requirements

### Requirement: Stable document-to-client association
The system SHALL bind a newly created document to exactly one same-tenant client and SHALL include the client identity in ingestion idempotency fingerprints and document provenance.

#### Scenario: Existing document is submitted through another client
- **WHEN** a source and external document identifier already identify a document associated with a different client in the same tenant
- **THEN** the system returns `409` without creating a version, changing the association, or queuing indexing

#### Scenario: Ingestion idempotency is replayed through another client
- **WHEN** an idempotency key is reused with a different client identity
- **THEN** the system treats the request as an idempotency conflict and leaves all document records unchanged

### Requirement: Preserved legacy document lineage
The system SHALL preserve documents that predate client association as explicitly unassociated legacy records, SHALL keep them searchable and retrievable under their existing tenant authorization, and SHALL require a client for every new ingestion after this capability is deployed.

#### Scenario: Existing database is migrated
- **WHEN** the client-association schema is applied to existing documents
- **THEN** their identities, versions, chunks, embeddings, search behavior, and authorization lineage remain unchanged and their client association is explicitly absent
