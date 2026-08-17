## ADDED Requirements

### Requirement: Preserve field-specific document admission
The system SHALL record whether title, content, or semantic evidence admitted each document. Exact and prefix title matches SHALL survive content-reranker rejection. Content-only and semantic-only candidates SHALL still pass final admission.

#### Scenario: Exact title is absent from content
- **WHEN** an exact current title matches but its content fails reranking
- **THEN** the document remains a general result

#### Scenario: Title prefix is absent from content
- **WHEN** a current title prefix matches but its content fails reranking
- **THEN** the document remains a general result

#### Scenario: Content-only candidate fails
- **WHEN** a candidate has no title match and fails final admission
- **THEN** it is not returned

#### Scenario: Title and passage both match
- **WHEN** one document has title and passage evidence
- **THEN** the system returns one deterministic result with its best admitted passage

#### Scenario: Search is degraded
- **WHEN** embedding or reranking fails but title retrieval succeeds
- **THEN** the title match remains eligible under the degraded policy

