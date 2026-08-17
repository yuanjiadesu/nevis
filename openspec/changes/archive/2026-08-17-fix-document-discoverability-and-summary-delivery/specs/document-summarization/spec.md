## ADDED Requirements

### Requirement: Reconcile fictional summary work
The system SHALL provide an operator command for enabled fictional deployments. It SHALL create missing work only for eligible current versions. It SHALL report failed work by default and retry it only when explicitly requested. Repeated runs SHALL not duplicate work.

#### Scenario: Current version has no work
- **WHEN** reconciliation finds an eligible current version without a summary row
- **THEN** it creates one pending row without calling the provider

#### Scenario: Reconciliation repeats
- **WHEN** pending or ready work already exists
- **THEN** no duplicate is created

#### Scenario: Failed work is found
- **WHEN** failed work exists and retry was not requested
- **THEN** the command reports it safely without requeuing it

#### Scenario: Failed work is retried
- **WHEN** the operator explicitly retries failed work
- **THEN** eligible work is requeued once with audit lineage and bounded attempts

#### Scenario: Deployment is ineligible
- **WHEN** summaries or fictional-data mode are disabled
- **THEN** reconciliation refuses before creating work or sending content

#### Scenario: Historical version lacks work
- **WHEN** a non-current version has no summary row
- **THEN** default reconciliation ignores it

### Requirement: Expose summary lifecycle
Each current version SHALL have one state: `not_requested`, `pending`, `processing`, `ready`, or `failed`. Summary state SHALL not affect indexing or document access and SHALL not expose sensitive data.

#### Scenario: No row exists
- **WHEN** a current version has no summary row
- **THEN** its state is `not_requested`

#### Scenario: Work is active
- **WHEN** work is queued or leased
- **THEN** its state is `pending` or `processing`

#### Scenario: Work succeeds
- **WHEN** bounded generation succeeds
- **THEN** its state is `ready` and its summary is available

#### Scenario: Work fails
- **WHEN** work fails permanently
- **THEN** its state is `failed`, no summary is exposed, and the document remains available

