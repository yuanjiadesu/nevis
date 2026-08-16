## Purpose

Provide a tenant and advisor authorization boundary that protects advisory data before any retrieval capability can expose it, while retaining a durable decision trail for every protected action.

## ADDED Requirements

### Requirement: Tenant and advisor membership model
The system SHALL represent tenants, advisors, and active advisor-to-tenant memberships. It SHALL bootstrap `nevis-global` as the initial tenant and migrate the existing platform corpus into that tenant without losing document, version, chunk, vector, or audit identities.

#### Scenario: Existing platform data is upgraded
- **WHEN** the tenant authorization schema is applied to a database containing the bootstrap corpus
- **THEN** all existing corpus records are owned by the `nevis-global` tenant and remain attributable to their original source, document version, and embedding profile

#### Scenario: An advisor belongs to a tenant
- **WHEN** an active advisor membership is established for a tenant
- **THEN** the system can identify that advisor as an authorized subject for actions scoped to that tenant

### Requirement: Explicit authorization context and decision
The system SHALL require a tenant-scoped advisor context for protected document actions and SHALL persist an allow or deny decision with a policy identifier, request identifier, tenant, advisor, action, occurrence time, and credential-safe metadata.

#### Scenario: An authorized advisor performs a protected action
- **WHEN** an advisor with an active membership requests a protected action within that tenant
- **THEN** the system permits the action and records its allow decision in the audit trail

#### Scenario: A non-member requests a protected action
- **WHEN** an advisor without an active membership requests a protected action for a tenant
- **THEN** the system denies the action, creates no protected resource or state change, and records the deny decision without exposing protected data

### Requirement: Pre-retrieval authorization predicate
The system SHALL provide a reusable authorization predicate that limits candidate document records to the requested tenant and an allowed advisor membership before any future retrieval, ranking, or result construction occurs.

#### Scenario: A future retrieval is authorized
- **WHEN** a future retrieval capability receives an allowed advisor context for a tenant
- **THEN** it can consider only records owned by that tenant and permitted by the recorded authorization decision

#### Scenario: A future retrieval is denied
- **WHEN** a future retrieval capability receives a denied advisor context
- **THEN** it returns no protected result, score, count, or provenance metadata from the requested or any other tenant

### Requirement: Authorization lineage for protected data
The system SHALL retain a tenant, source, document version, embedding profile, and authorization-decision reference for every indexed record that can later be retrieved.

#### Scenario: Indexed data is inspected for provenance
- **WHEN** an operator or future authorized retrieval inspects an indexed record
- **THEN** its tenant ownership and the decision context governing its indexing are available alongside its source, document version, and embedding profile
