## MODIFIED Requirements

### Requirement: Plain-text document ingestion
The system SHALL accept a tenant-authorized plain-text document submission containing a source reference, stable external document identifier, title, content, and idempotency key, and SHALL return the document-version identity and indexing status.

#### Scenario: New document is accepted
- **WHEN** an authorized advisor submits a valid document for a tenant with an unseen source and external document identifier
- **THEN** the system creates a source, document, first immutable document version, and queued indexing work under that tenant

#### Scenario: Document content is updated
- **WHEN** an authorized advisor submits different normalized content for an existing source and external document identifier in the same tenant
- **THEN** the system creates a new immutable version and queues indexing only for that new version

### Requirement: Idempotent ingestion
The system SHALL make an ingestion request idempotent within its authorized tenant using its idempotency key and SHALL retain a content hash for each version.

#### Scenario: Request is replayed
- **WHEN** an authorized caller repeats an accepted submission with the same tenant and idempotency key
- **THEN** the system returns the original document-version identity and does not create another version or indexing job

#### Scenario: Idempotency key conflicts
- **WHEN** a caller reuses an idempotency key with a different request payload in the same tenant
- **THEN** the system rejects the request without creating or modifying document records

### Requirement: Immutable document provenance
The system SHALL retain each document version's tenant ownership, source identity, document identity, version number, normalized-content hash, creation time, and authorization decision without application-level mutation or deletion.

#### Scenario: Earlier version remains attributable
- **WHEN** a later version of a document is ingested
- **THEN** the earlier version remains addressable with its original tenant, provenance, authorization decision, and content hash

### Requirement: Audited ingestion decisions
The system SHALL record an audit event for allowed, denied, accepted, rejected, and idempotently replayed ingestion requests with the tenant and authorization decision, without logging document content or idempotency keys.

#### Scenario: Ingestion outcome is recorded
- **WHEN** an ingestion request reaches an outcome
- **THEN** its audit event identifies the request, tenant, advisor, outcome, document-version identity when available, and authorization decision using credential-safe metadata
