## MODIFIED Requirements

### Requirement: Return result and audit provenance

The system SHALL attribute every client result to tenant, client, creation decision, and search decision. It SHALL attribute every document result to tenant, client, source, document, current version, embedding profile, indexing decision, and search decision.

Every document result SHALL include the client’s display name. Search audit records SHALL exclude raw queries, snippets, client personal data, document content, vectors, and provider credentials.

#### Scenario: Search returns mixed results

- **WHEN** one response contains clients and documents
- **THEN** each result identifies its type, lineage, and search authorisation decision

#### Scenario: Search returns a document

- **WHEN** a document result is returned
- **THEN** it includes client identity and display name

#### Scenario: Search completes

- **WHEN** an allowed search returns hybrid, degraded, or empty results
- **THEN** audit records store fingerprint, result identities, policy version, mode, bounded scores, count, and latency without content
