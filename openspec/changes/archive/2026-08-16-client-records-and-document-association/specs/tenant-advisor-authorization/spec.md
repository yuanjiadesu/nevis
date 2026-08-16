## MODIFIED Requirements

### Requirement: Explicit authorization context and decision
The system SHALL require an authenticated advisor identity and an explicit tenant for protected client and document actions and SHALL persist an allow or deny decision with a policy identifier, request identifier, tenant, advisor, action, identity mode, occurrence time, and credential-safe metadata. In production, the advisor external identity SHALL come only from the verified OIDC subject; request headers or bodies SHALL NOT override it.

#### Scenario: An authorized advisor performs a protected action
- **WHEN** an authenticated advisor with an active membership requests a protected client or document action within that tenant
- **THEN** the system permits the action and records its allow decision with safe identity context in the audit trail

#### Scenario: A non-member requests a protected action
- **WHEN** an authenticated advisor without an active membership requests a protected client or document action for a tenant
- **THEN** the system denies the action, creates no protected resource or state change, and records the deny decision without exposing protected data

#### Scenario: Authenticated subject does not map to an advisor
- **WHEN** a verified production subject has no active advisor record
- **THEN** the system returns a generic `403`, records a credential-safe denied decision when a valid tenant can be resolved, and exposes no protected data

#### Scenario: Advisor header attempts to override production identity
- **WHEN** a protected production request supplies an advisor header in addition to a valid bearer token
- **THEN** the header cannot change the authenticated advisor identity or tenant authorization outcome

#### Scenario: Tenant context is missing or unknown
- **WHEN** an authenticated advisor submits a protected request without an explicit valid tenant identifier
- **THEN** the system rejects the request before protected data access and does not infer a tenant from token claims or unrelated memberships

### Requirement: Pre-retrieval authorization predicate
The system SHALL provide reusable authorization predicates that limit candidate client and document records to the requested tenant and an allowed advisor membership before lookup, ranking, aggregation, result construction, or existence checks occur.

#### Scenario: A future retrieval is authorized
- **WHEN** a retrieval capability receives an allowed advisor context for a tenant
- **THEN** it can consider only client or document records owned by that tenant and permitted by the recorded authorization decision

#### Scenario: A future retrieval is denied
- **WHEN** a retrieval capability receives a denied advisor context
- **THEN** it returns no protected result, score, count, existence signal, or provenance metadata from the requested or any other tenant
