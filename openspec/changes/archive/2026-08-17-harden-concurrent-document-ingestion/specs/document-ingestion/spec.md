## ADDED Requirements

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
