## Purpose

Let authorised advisers revise client documents while preserving immutable, auditable history.

## ADDED Requirements

### Requirement: Return editable document content

The system SHALL return current title, plain-text content, version identity, and version number only through an authorised edit representation. Unknown and cross-tenant documents SHALL share the same `404`.

#### Scenario: Adviser opens a document for editing

- **WHEN** an authorised adviser requests an associated same-tenant document
- **THEN** the system returns title, content, document identity, and current version identity

#### Scenario: Adviser opens an inaccessible document

- **WHEN** an adviser requests an unknown or cross-tenant document
- **THEN** the system returns `404` without metadata or content

### Requirement: Create an explicit revision

The system SHALL accept an authorised title, replacement plain text, and idempotency key for an associated document. It SHALL reuse existing source and external identity. Changed normalized content SHALL create and index the next immutable version.

#### Scenario: Adviser saves changed content

- **WHEN** an authorised adviser submits changed normalized content
- **THEN** the system creates the next version and returns its identity and indexing state

#### Scenario: Adviser saves unchanged content

- **WHEN** submitted normalized content matches the current version
- **THEN** the system returns the current version without another version or indexing job

#### Scenario: Adviser revises a legacy document

- **WHEN** an adviser submits a revision for a document without a client
- **THEN** the system rejects it without changing versions or association

### Requirement: Support revisions in the console

The console SHALL pre-fill title and plain-text content for listed client documents. It SHALL create a revision, refresh the timeline, and distinguish editing from adding a document.

#### Scenario: Adviser revises a listed document

- **WHEN** an adviser edits and saves a listed document
- **THEN** one document remains, its current version advances, and the old version appears in history
