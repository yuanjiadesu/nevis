# client-records Specification

## Purpose

Provide durable tenant-owned client records that authorized advisors can create, retrieve, and match safely within an explicitly authorized tenant.

## Requirements

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

### Requirement: Tenant-authorized client matching
The system SHALL match clients only within the explicitly authorized tenant using case-insensitive normalized email, name, and description evidence, and SHALL NOT return or score clients from another tenant.

#### Scenario: Authorized client match
- **WHEN** an authorized advisor searches for a normalized email, client name, or description text present in their tenant
- **THEN** the client can appear as a typed client result with bounded fields and complete client-search provenance

#### Scenario: Stronger client match exists in another tenant
- **WHEN** a stronger matching client exists only in another tenant
- **THEN** that client does not affect candidates, ranking, pagination, counts, or response metadata

#### Scenario: Client query has no lexical evidence
- **WHEN** no authorized client email, name, or description provides relevant lexical evidence
- **THEN** client matching contributes no arbitrary or fuzzy client candidate

### Requirement: Deterministic client match precedence
The system SHALL prefer an exact normalized email match, then an exact case-insensitive full-name match, before general name or description text matches, and SHALL apply a stable client-identity tie-breaker within equal match classes.

#### Scenario: Exact email and general text matches coexist
- **WHEN** one authorized client exactly matches the normalized query email and other clients match only name or description text
- **THEN** the exact-email client has the strongest client match class

#### Scenario: Equal client text matches coexist
- **WHEN** multiple authorized clients have the same client match class and rank score
- **THEN** their relative order is stable across identical requests and pagination

### Requirement: Client search representation and provenance
The system SHALL return a client search result with a client discriminator, client identity, bounded display name, email, optional bounded description excerpt, common rank score, tenant identity, creation authorization decision, and governing search authorization decision.

#### Scenario: Client result is returned
- **WHEN** a client is included in a search response
- **THEN** the caller can distinguish it from a document result and attribute it to the authorized tenant, client record, creation decision, and search decision

### Requirement: Tenant-authorized client directory
The system SHALL provide a bounded, stable, tenant-authorized paginated client directory that returns safe client summary fields and an opaque continuation cursor without disclosing clients, totals, or cursors from another tenant.

#### Scenario: Authorized directory page is requested
- **WHEN** an advisor with active membership requests a bounded directory page for an explicit tenant
- **THEN** the system returns only same-tenant client summaries in stable order with an opaque next cursor when another page exists

#### Scenario: Directory request is not authorized
- **WHEN** an identity without active membership requests a directory page for a tenant
- **THEN** the system returns `403` and returns no client summaries, totals, or pagination information

### Requirement: Tenant-authorized client update
The system SHALL allow an advisor with active membership to update the bounded editable fields of a same-tenant client and SHALL return the updated safe representation with an authorization decision identity.

#### Scenario: Authorized client is updated
- **WHEN** an authorized advisor submits a valid update for a client in the requested tenant
- **THEN** the system persists the allowed fields, returns the updated representation, and records the authorization outcome

#### Scenario: Target client is absent or cross-tenant
- **WHEN** an advisor requests an update for an unknown client identity or a client owned by another tenant
- **THEN** the system returns the same generic `404` response and changes no record
