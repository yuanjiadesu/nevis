## Purpose

Provide a controlled plain-text intake path that establishes immutable document provenance and auditability before the platform accepts untrusted files or serves retrieval.

## ADDED Requirements

### Requirement: Plain-text document ingestion
The system SHALL accept a plain-text document submission containing a source reference, stable external document identifier, title, content, and idempotency key, and SHALL return the document-version identity and indexing status.

#### Scenario: New document is accepted
- **WHEN** a valid submission has an unseen source and external document identifier
- **THEN** the system creates a source, document, first immutable document version, and queued indexing work under `nevis-global`

#### Scenario: Document content is updated
- **WHEN** a valid submission uses an existing source and external document identifier with different normalized content
- **THEN** the system creates a new immutable version and queues indexing only for that new version

### Requirement: Idempotent ingestion
The system SHALL make an ingestion request idempotent within `nevis-global` using its idempotency key and SHALL retain a content hash for each version.

#### Scenario: Request is replayed
- **WHEN** a caller repeats an accepted submission with the same idempotency key
- **THEN** the system returns the original document-version identity and does not create another version or indexing job

#### Scenario: Idempotency key conflicts
- **WHEN** a caller reuses an idempotency key with a different request payload
- **THEN** the system rejects the request without creating or modifying document records

### Requirement: Immutable document provenance
The system SHALL retain each document version's source identity, document identity, version number, normalized-content hash, creation time, and global ownership scope without application-level mutation or deletion.

#### Scenario: Earlier version remains attributable
- **WHEN** a later version of a document is ingested
- **THEN** the earlier version remains addressable with its original provenance and content hash

### Requirement: Audited ingestion decisions
The system SHALL record an audit event for accepted, rejected, and idempotently replayed ingestion requests with the `nevis-global` organization and `global-policy-v1 / allow` authorization decision, without logging document content or idempotency keys.

#### Scenario: Ingestion outcome is recorded
- **WHEN** an ingestion request reaches an outcome
- **THEN** its audit event identifies the request, outcome, document-version identity when available, and authorization decision using credential-safe metadata

### Requirement: Plain-text-only boundary
The system SHALL reject binary/file-upload ingestion and SHALL not perform PDF/DOCX extraction, OCR, object-storage writes, or malware scanning in this capability.

#### Scenario: File upload is attempted
- **WHEN** a caller submits a non-plain-text payload or file upload
- **THEN** the system returns a validation error and creates no document or indexing record
