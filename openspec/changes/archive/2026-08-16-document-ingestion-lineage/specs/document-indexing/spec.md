## Purpose

Convert accepted immutable plain-text document versions into deterministic chunks and embeddings through durable work while retaining the lineage required for future authorized retrieval.

## ADDED Requirements

### Requirement: Durable indexing lifecycle
The system SHALL create durable indexing work for each newly accepted document version and expose queued, processing, completed, and failed status for that version.

#### Scenario: Indexing work is queued
- **WHEN** a new document version is accepted
- **THEN** the system durably records queued indexing work before reporting acceptance

#### Scenario: Indexing fails
- **WHEN** chunking or embedding cannot complete
- **THEN** the system records a failed status and safe failure detail without marking the version as indexed

### Requirement: Deterministic chunk generation
The system SHALL derive ordered chunks deterministically from a document version using a versioned chunking configuration and SHALL retain each chunk's ordinal, character boundaries, and content hash.

#### Scenario: A version is processed
- **WHEN** indexing processes a document version
- **THEN** repeating the same content with the same chunking configuration produces the same ordered chunk boundaries and hashes

### Requirement: Embedding and provenance attribution
The system SHALL associate every generated vector with its organization, source, document, document version, chunk, active embedding profile, and authorization decision.

#### Scenario: A chunk is embedded
- **WHEN** the active embedding provider returns an embedding for a chunk
- **THEN** the persisted vector retains the complete provenance needed to attribute a future retrieval result

### Requirement: Safe worker execution and retry
The system SHALL process indexing work outside the ingestion request lifecycle and SHALL make retries safe from duplicate chunks or vectors for the same document-version and embedding-profile combination.

#### Scenario: Work is retried after interruption
- **WHEN** indexing work is retried after a worker interruption
- **THEN** the system resumes or reprocesses the version without creating duplicate persisted chunk/vector identities

### Requirement: Indexing status visibility
The system SHALL expose document-version indexing status and credential-safe failure information without exposing raw document content, chunk text, provider credentials, or vectors.

#### Scenario: Caller checks a version
- **WHEN** a caller requests the status of an accepted document version
- **THEN** the system returns its lifecycle state and timestamps, with a safe error classification when it failed
