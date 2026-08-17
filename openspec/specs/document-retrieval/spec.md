# document-retrieval Specification

## Purpose

Expose a safe tenant-authorized document resource view with its client association, current-version indexing state, and complete retrieval provenance.

## Requirements

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

### Requirement: Tenant-authorized client document timeline
The system SHALL provide a bounded, stable list of documents associated with an authorized same-tenant client, including safe current-version indexing state, `summary: string | null`, and a continuation cursor, without returning document content. Summary availability SHALL NOT change membership, order, or pagination.

#### Scenario: Authorized client document timeline is requested
- **WHEN** an advisor with active membership requests a bounded document timeline for a client in the explicit tenant
- **THEN** the system returns only documents associated with that client, their safe current version state, nullable summaries, and an opaque next cursor when another page exists

#### Scenario: Timeline mixes summary states
- **WHEN** a client document timeline contains ready and absent summaries
- **THEN** all documents retain their existing order and pagination

#### Scenario: Client is absent or cross-tenant
- **WHEN** an advisor requests a document timeline for an unknown client identity or a client owned by another tenant
- **THEN** the system returns the same generic `404` response and no document metadata

### Requirement: Tenant-authorized document version timeline
The system SHALL provide the immutable version history of an authorized document without returning version content, and SHALL distinguish a missing/cross-tenant document using the existing generic `404` behavior.

#### Scenario: Authorized document history is requested
- **WHEN** an advisor with active membership requests an authorized document’s version history
- **THEN** the system returns each immutable version’s identity, ordinal, creation time, and indexing state in stable order

### Requirement: Return summary availability
Safe document resources and client timelines SHALL return `summary_status` and nullable `summary`. Only `ready` SHALL include summary text. State SHALL not affect authorization, ordering, or pagination.

#### Scenario: Summary is ready
- **WHEN** an authorized adviser retrieves a ready summary
- **THEN** the response returns `summary_status: ready` and bounded text

#### Scenario: Summary was not requested
- **WHEN** no summary row exists
- **THEN** the response returns `summary_status: not_requested` and `summary: null`

#### Scenario: Summary is active
- **WHEN** work is queued or processing
- **THEN** the response returns its state and `summary: null` without delay

#### Scenario: Summary failed
- **WHEN** summary work failed
- **THEN** the response returns `summary_status: failed` and `summary: null` without provider details

#### Scenario: Timeline has mixed states
- **WHEN** timeline rows have different summary states
- **THEN** each row reports its state without changing order or cursors

#### Scenario: Console shows state
- **WHEN** a document appears in the console
- **THEN** ready text is labelled AI-generated and absent text has a concise state label
