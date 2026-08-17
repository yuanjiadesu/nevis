# document-revision Specification

## Purpose
Allow authorized advisors to revise client documents while retaining an immutable, auditable history of every accepted version.

## Requirements

### Requirement: Authorized document edit representation
The system SHALL expose the current title, plain-text content, current version identity, and version number only through an authorized document edit representation. It SHALL return the same generic `404` for an unknown document and a document outside the advisor's authorized tenant.

#### Scenario: Advisor opens an associated document for editing
- **WHEN** an authorized advisor requests the edit representation for a client-associated document in their tenant
- **THEN** the system returns the current title and plain-text content together with its document and current version identities

#### Scenario: Advisor opens an inaccessible document for editing
- **WHEN** an advisor requests the edit representation for an unknown or cross-tenant document
- **THEN** the system returns a generic `404` and exposes no document metadata or content

### Requirement: Explicit document revision
The system SHALL accept an authorized revision request for a client-associated document containing a title, replacement plain-text content, and idempotency key. It SHALL use that document's existing source and external document identity, create the next immutable version only when normalized content differs, and queue indexing for a newly created version.

#### Scenario: Advisor saves changed content
- **WHEN** an authorized advisor submits changed normalized text for an associated document
- **THEN** the system creates the next sequential immutable version for the same document and returns its version identity and indexing status

#### Scenario: Advisor saves unchanged content
- **WHEN** an authorized advisor submits content whose normalized form matches the current version
- **THEN** the system returns the current version without creating a duplicate version or indexing job

#### Scenario: Legacy document is revised
- **WHEN** an advisor submits a revision for a document that has no client association
- **THEN** the system rejects the request without creating a version or changing its association

### Requirement: Revision console workflow
The advisor console SHALL provide an edit action for each listed client document, prefill the current title and plain-text content, and refresh that document's timeline after an accepted revision. It SHALL distinguish an existing document revision from adding a new document.

#### Scenario: Advisor revises a listed document
- **WHEN** an advisor selects Edit document, changes the content, and saves
- **THEN** the document remains one timeline record, its displayed current version advances, and its earlier version appears in history
