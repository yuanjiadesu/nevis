## ADDED Requirements

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
