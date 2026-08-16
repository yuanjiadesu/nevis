## MODIFIED Requirements

### Requirement: Embedding and provenance attribution
The system SHALL associate every generated vector with its tenant, source, document, document version, chunk, active embedding profile, and authorization decision.

#### Scenario: A chunk is embedded
- **WHEN** the active embedding provider returns an embedding for a chunk
- **THEN** the persisted vector retains the complete tenant and decision provenance needed to attribute and authorize a future retrieval result
