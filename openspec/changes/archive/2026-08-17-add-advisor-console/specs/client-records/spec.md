## ADDED Requirements

### Requirement: List authorised clients

The system SHALL return a bounded, stable, tenant-authorised client page with safe fields and an opaque cursor. It SHALL not disclose another tenant’s clients, totals, or cursors.

#### Scenario: Adviser requests a directory page

- **WHEN** an adviser with active membership requests a bounded page for a tenant
- **THEN** the system returns same-tenant clients in stable order and a cursor when another page exists

#### Scenario: Adviser lacks membership

- **WHEN** an identity without active membership requests a tenant page
- **THEN** the system returns `403` without clients, totals, or pagination data

### Requirement: Update an authorised client

The system SHALL let an adviser with active membership update bounded fields on a same-tenant client. It SHALL return the safe client and authorisation decision.

#### Scenario: Adviser updates a client

- **WHEN** an authorised adviser submits valid fields for a same-tenant client
- **THEN** the system stores the fields, returns the client, and records authorisation

#### Scenario: Client is absent or cross-tenant

- **WHEN** an adviser updates an unknown or cross-tenant client
- **THEN** the system returns the same `404` and changes no record
