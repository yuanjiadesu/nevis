## ADDED Requirements

### Requirement: Enforce summary-worker parity
When summaries are enabled, the API SHALL require a fresh worker heartbeat with matching non-secret enabled state, provider, model, and prompt identity. Disabled deployments SHALL not require a summary provider or heartbeat.

#### Scenario: Configuration matches
- **WHEN** a fresh worker heartbeat matches the API
- **THEN** summary delivery is ready

#### Scenario: Worker is missing
- **WHEN** the API enables summaries but the worker heartbeat is missing or stale
- **THEN** readiness fails with a safe diagnostic

#### Scenario: Configuration differs
- **WHEN** API and worker summary identities differ
- **THEN** readiness fails without exposing sensitive data

#### Scenario: Summaries are disabled
- **WHEN** summaries are consistently disabled
- **THEN** normal readiness needs no summary provider or heartbeat

### Requirement: Report summary diagnostics
An operator diagnostic SHALL report bounded current-version state counts, safe failure counts, and heartbeat freshness. It SHALL omit documents, clients, summaries, prompts, provider responses, endpoints, and credentials.

#### Scenario: Operator checks delivery
- **WHEN** the diagnostic runs
- **THEN** it distinguishes disabled, missing, delayed, and failed delivery

#### Scenario: Output is produced
- **WHEN** the diagnostic returns data
- **THEN** it contains no sensitive content

### Requirement: Verify the UAT pipeline
The fictional-data user acceptance testing (UAT) environment SHALL provide a bounded check that ingests or revises a document, waits for indexing and summary work, verifies exact-title search, and verifies a ready labelled summary.

#### Scenario: Pipeline is healthy
- **WHEN** dependencies and API-worker configuration are valid
- **THEN** the version is indexed, searchable by an unrelated exact title, and reaches `ready`

#### Scenario: Pipeline fails
- **WHEN** any stage fails
- **THEN** the check reports the stage safely and does not report success
