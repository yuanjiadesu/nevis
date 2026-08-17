# document-ingestion Specification

## Purpose

Provide a controlled plain-text intake path that establishes immutable document provenance and auditability before the platform accepts untrusted files or serves retrieval.

## Requirements

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

### Requirement: Idempotent ingestion
The system SHALL make an ingestion request idempotent within its authorized tenant using its idempotency key and SHALL retain a content hash for each version.

#### Scenario: Request is replayed
- **WHEN** an authorized caller repeats an accepted submission with the same tenant and idempotency key
- **THEN** the system returns the original document-version identity and does not create another version or indexing job

#### Scenario: Idempotency key conflicts
- **WHEN** a caller reuses an idempotency key with a different request payload in the same tenant
- **THEN** the system rejects the request without creating or modifying document records

### Requirement: Deterministic concurrent ingestion
The system SHALL serialize submissions that share a tenant and logical document or idempotency key. It SHALL return an accepted, replayed, or conflict outcome without exposing an internal database conflict.

#### Scenario: Equivalent requests arrive together
- **WHEN** concurrent submissions use the same tenant, idempotency key, and payload
- **THEN** one submission is accepted, the other is replayed, and only one document version and indexing job exist

#### Scenario: Concurrent revisions target one document
- **WHEN** concurrent submissions use different idempotency keys and content for the same tenant, source, and external document identifier
- **THEN** each submission creates a distinct sequential version and queues one indexing job

#### Scenario: Concurrent requests conflict on idempotency
- **WHEN** concurrent submissions reuse one tenant and idempotency key with different payloads
- **THEN** one submission succeeds and the other returns `409` without creating records for the rejected payload

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

### Requirement: Plain-text-only boundary
The system SHALL reject binary/file-upload ingestion and SHALL not perform PDF/DOCX extraction, OCR, object-storage writes, or malware scanning in this capability.

#### Scenario: File upload is attempted
- **WHEN** a caller submits a non-plain-text payload or file upload
- **THEN** the system returns a validation error and creates no document or indexing record

### Requirement: Stable document-to-client association
The system SHALL bind every document to exactly one same-tenant client, SHALL reject any document record that has no client, and SHALL include the client identity in ingestion idempotency fingerprints and document provenance.

#### Scenario: Existing document is submitted through another client
- **WHEN** a source and external document identifier already identify a document associated with a different client in the same tenant
- **THEN** the system returns `409` without creating a version, changing the association, or queuing indexing

#### Scenario: Ingestion idempotency is replayed through another client
- **WHEN** an idempotency key is reused with a different client identity
- **THEN** the system treats the request as an idempotency conflict and leaves all document records unchanged

#### Scenario: Document revision reuses the existing association
- **WHEN** an advisor submits a new version of an existing document
- **THEN** the system reuses that document's client association without requiring the advisor to restate it
