## Purpose

Provide durable tenant-owned client records that authorized advisors can create and retrieve safely before client search is introduced.

## ADDED Requirements

### Requirement: Tenant-authorized client creation
The system SHALL allow an authenticated advisor with an active membership in the explicitly requested tenant to create a client with bounded first name, last name, email, description, social links, and source provenance, and SHALL return the client identity, normalized record, creation time, and authorization-decision identity.

#### Scenario: Valid client is created
- **WHEN** an authorized advisor submits a valid client for a tenant
- **THEN** the system creates exactly one client owned by that tenant and returns its safe representation and creation authorization lineage

#### Scenario: Client creation is not authorized
- **WHEN** an authenticated advisor without active membership requests client creation for a tenant
- **THEN** the system returns `403`, creates no client or idempotency record, and exposes no tenant data

### Requirement: Tenant-scoped case-insensitive email uniqueness
The system SHALL trim and case-normalize client email for identity comparison and SHALL enforce uniqueness on that normalized value within each tenant while allowing the same normalized email in different tenants.

#### Scenario: Email differs only by case or surrounding whitespace
- **WHEN** a tenant already contains a client whose normalized email equals the submitted email
- **THEN** the system returns `409` and does not create or modify a client

#### Scenario: Same email is used in another tenant
- **WHEN** an authorized advisor submits an email whose normalized value exists only in another tenant
- **THEN** the system can create the client without disclosing the other tenant's record

### Requirement: Idempotent client creation
The system SHALL make client creation idempotent within the authorized tenant using a bounded idempotency key and a fingerprint of the normalized request.

#### Scenario: Identical creation request is replayed
- **WHEN** an authorized caller repeats an accepted client creation with the same tenant, idempotency key, and normalized payload
- **THEN** the system returns the original client identity and records a replay without creating another client

#### Scenario: Client idempotency key conflicts
- **WHEN** a caller reuses a client-creation idempotency key with a different normalized payload in the same tenant
- **THEN** the system returns `409` and creates or modifies no client

### Requirement: Tenant-scoped client retrieval
The system SHALL retrieve a client only through the authorized tenant relation and SHALL return its fields, source provenance, creation authorization decision, and timestamps without returning records, counts, or existence signals from another tenant.

#### Scenario: Client is retrieved in its tenant
- **WHEN** an authorized advisor requests a client owned by the explicitly requested tenant
- **THEN** the system returns that client with its tenant, source, and creation authorization lineage

#### Scenario: Client is missing or belongs to another tenant
- **WHEN** an authorized advisor requests an unknown client identity or one owned by another tenant
- **THEN** the system returns the same generic `404` response in either case

### Requirement: Audited client outcomes
The system SHALL record credential-safe audit events for allowed, denied, created, replayed, conflicted, found, and not-found client operations without recording raw email, description, social links, idempotency keys, or identity credentials.

#### Scenario: Client operation reaches an outcome
- **WHEN** a client create or retrieval request reaches an outcome
- **THEN** the audit trail identifies the request, tenant, advisor when known, outcome, client identity when safely available, and authorization decision using bounded metadata
