# global-data-lineage Specification

## Purpose

Establish the global ownership and audit lineage needed for later client and document retrieval while intentionally retaining the initial global access model.

## Requirements

### Requirement: Global organization baseline
The system SHALL persist `nevis-global` as the initial tenant, identified by the stable slug `nevis-global`, and use its tenant identity as the ownership scope for existing bootstrap platform data.

#### Scenario: Fresh database initialization
- **WHEN** the platform schema is initialized on a new database
- **THEN** the `nevis-global` tenant exists exactly once and can be referenced by later tenant-owned platform records

#### Scenario: Existing bootstrap data is migrated
- **WHEN** a database with the former global organization baseline is upgraded
- **THEN** its data remains owned by the `nevis-global` tenant without losing lineage identities

### Requirement: Append-only audit event foundation
The system SHALL persist audit events with an event type, occurrence time, tenant identifier, request identifier, authorization policy identifier, authorization result, and structured metadata.

#### Scenario: A platform action is audited
- **WHEN** a platform action emits an audit event
- **THEN** the event retains the tenant and authorization-decision context required to attribute the action

#### Scenario: An audit event is stored
- **WHEN** an audit event has been persisted
- **THEN** application behavior does not provide an operation that modifies or deletes that event

### Requirement: Explicit global authorization decision
The system SHALL replace the bootstrap-wide `global-policy-v1 / allow` decision with an explicit tenant-scoped authorization decision for protected actions, while retaining historical audit events as immutable records.

#### Scenario: A first-release action evaluates access
- **WHEN** a platform action requires an authorization decision
- **THEN** it records a tenant-scoped policy identifier and allow or deny result associated with the requesting advisor and tenant
