## Purpose

Expose a safe tenant-authorized document resource view with its client association, current-version indexing state, and complete retrieval provenance.

## ADDED Requirements

### Requirement: Tenant-scoped document retrieval
The system SHALL retrieve a document only through the authorized tenant relation and SHALL NOT reveal a document, count, client association, or existence signal from another tenant.

#### Scenario: Document is retrieved in its tenant
- **WHEN** an authorized advisor requests a document owned by the explicitly requested tenant
- **THEN** the system returns its safe document resource representation

#### Scenario: Document is missing or belongs to another tenant
- **WHEN** an authorized advisor requests an unknown document identity or one owned by another tenant
- **THEN** the system returns the same generic `404` response in either case

### Requirement: Current document state and lineage
The system SHALL return the document identity, title, source, client association when present, current immutable version, current indexing status, tenant identity, originating ingestion authorization decision, and retrieval authorization decision without returning document content.

#### Scenario: Associated current document is returned
- **WHEN** an authorized advisor retrieves a document created through client-scoped ingestion
- **THEN** the representation attributes it to its tenant, client, source, current version, indexing state, ingestion decision, and retrieval decision

#### Scenario: Preserved legacy document is returned
- **WHEN** an authorized advisor retrieves a document that predates mandatory client association
- **THEN** the representation explicitly reports no client association while retaining the document's existing tenant and ingestion lineage

### Requirement: Audited document retrieval
The system SHALL record credential-safe audit events for found and not-found document retrieval outcomes, linked to the retrieval authorization decision, without recording document content.

#### Scenario: Document retrieval reaches an outcome
- **WHEN** an authorized document retrieval request returns a document or `404`
- **THEN** the audit trail records the bounded outcome and document identity only when safely available
