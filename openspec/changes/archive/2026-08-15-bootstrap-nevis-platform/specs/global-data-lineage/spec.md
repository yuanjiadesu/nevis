## Purpose

Establish the global ownership and audit lineage needed for later client and document retrieval while intentionally retaining the initial global access model.

## ADDED Requirements

### Requirement: Global organization baseline
The system SHALL persist exactly one bootstrap organization identified by the stable slug `nevis-global` and use it as the ownership scope for first-release platform data.

#### Scenario: Fresh database initialization
- **WHEN** the platform schema is initialized on a new database
- **THEN** the `nevis-global` organization exists exactly once and can be referenced by later platform records

### Requirement: Append-only audit event foundation
The system SHALL persist audit events with an event type, occurrence time, organization identifier, request identifier, authorization policy identifier, authorization result, and structured metadata.

#### Scenario: A platform action is audited
- **WHEN** a platform action emits an audit event
- **THEN** the event retains the organization and authorization-decision context required to attribute the action

#### Scenario: An audit event is stored
- **WHEN** an audit event has been persisted
- **THEN** application behavior does not provide an operation that modifies or deletes that event

### Requirement: Explicit global authorization decision
The system SHALL represent the first-release access decision as `global-policy-v1` with an allow result, without implementing authentication, advisor roles, or tenant-specific filtering.

#### Scenario: A first-release action evaluates access
- **WHEN** a platform action requires an authorization decision
- **THEN** it records `global-policy-v1` and an allow result associated with `nevis-global`
