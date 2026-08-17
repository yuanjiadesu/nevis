## MODIFIED Requirements

### Requirement: Tenant-authorized client matching

The system SHALL match clients only within the explicitly authorized tenant using case-insensitive normalized email, name, and description evidence, and SHALL NOT return or score clients from another tenant. When no such evidence exists, the system MAY contribute bounded trigram candidates from client full names above an explicit similarity floor, and SHALL NOT apply trigram matching to client email or description fields or contribute any client candidate below that floor.

#### Scenario: Authorized client match

- **WHEN** an authorized advisor searches for a normalized email, client name, or description text present in their tenant
- **THEN** the client can appear as a typed client result with bounded fields and complete client-search provenance

#### Scenario: Stronger client match exists in another tenant

- **WHEN** a stronger matching client exists only in another tenant
- **THEN** that client does not affect candidates, ranking, pagination, counts, or response metadata

#### Scenario: Client query is a near miss of an identity field

- **WHEN** no authorized client email, name, or description provides relevant lexical evidence and the query is a near miss of a client full name in that tenant
- **THEN** that client can appear as a bounded trigram client result with complete client-search provenance

#### Scenario: Client query has no lexical evidence

- **WHEN** no authorized client email, name, or description provides relevant lexical evidence and no client full name reaches the similarity floor
- **THEN** client matching contributes no arbitrary client candidate

#### Scenario: Misspelled complete client email

- **WHEN** an advisor submits a complete email address that differs from an authorized client's email
- **THEN** the literal identifier route does not apply trigram matching and contributes no approximate client
