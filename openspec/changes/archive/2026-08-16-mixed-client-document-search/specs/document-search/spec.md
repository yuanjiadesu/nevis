## MODIFIED Requirements

### Requirement: Authorization precedes candidate retrieval
The system SHALL require an allowed tenant-scoped advisor authorization decision for mixed search and SHALL constrain client lexical, document lexical, and document semantic candidate sets to that tenant before scoring, ranking, aggregation, merging, counting, or result construction.

#### Scenario: Authorized tenant search
- **WHEN** an advisor with an active membership submits a valid search for a tenant
- **THEN** every client and document candidate considered by the search belongs to that tenant

#### Scenario: Missing or inactive membership
- **WHEN** a protected search has no valid advisor context or the advisor lacks an active membership in the asserted tenant
- **THEN** the system returns no client or document result, count, score, snippet, or provenance data and records a denied decision

#### Scenario: Matching content exists in another tenant
- **WHEN** an authorized advisor searches their tenant and a stronger matching client or document exists only in another tenant
- **THEN** the other tenant's record does not affect candidate sets, ordering, pagination, or response metadata

### Requirement: Stable bounded search contract
The system SHALL validate normalized query text and page size, return one list of discriminated client and document results, return an opaque cursor for additional results, and apply a total deterministic order using match class, common rank score, result type, and stable record identity.

#### Scenario: First page has more results
- **WHEN** a valid search has more authorized client and document results than the requested bounded page size
- **THEN** the response includes an opaque next cursor that continues the same query, tenant, embedding profile, retrieval mode, and mixed-ranking version after the final returned result

#### Scenario: Cursor context is invalid
- **WHEN** a cursor is malformed, modified, expired, or belongs to another query, tenant, profile, retrieval mode, or mixed-ranking version
- **THEN** the system rejects it without revealing search results or internal cursor state

#### Scenario: Query is invalid
- **WHEN** normalized query text is empty or exceeds the documented bound, or the requested limit is outside its allowed range
- **THEN** the system returns a validation error without executing retrieval

### Requirement: Result and audit provenance
The system SHALL make every client result attributable to its tenant, client, creation authorization decision, and search authorization decision, and every document result attributable to its tenant, client association when present, source, document, current document version, embedding profile, indexing authorization decision, and search authorization decision. It SHALL persist a credential-safe mixed-search audit record without raw query text, snippets, client PII, document content, vectors, or provider credentials.

#### Scenario: Search result is returned
- **WHEN** client and document results are included in one response
- **THEN** each result's discriminator and provenance identify its required type-specific lineage and the common search authorization decision

#### Scenario: Search completes
- **WHEN** an allowed search succeeds in hybrid, lexical-degraded, or empty-result mode
- **THEN** the audit trail records a query fingerprint, typed result identities, mixed-ranking version, retrieval mode, bounded score metadata, result count, and latency without recording raw customer content

## ADDED Requirements

### Requirement: Deterministic mixed client and document ranking
The system SHALL combine independently ranked authorized client and document candidates into one deterministic list without comparing raw lexical and semantic scores directly. Exact client identity matches SHALL receive their defined precedence, and remaining candidates SHALL use a versioned rank-fusion policy with stable type and identity tie-breakers.

#### Scenario: Client and document matches coexist
- **WHEN** a query has authorized client and current-document matches
- **THEN** the response contains both result types in one total order produced by the declared mixed-ranking version

#### Scenario: Exact client identity match coexists with document evidence
- **WHEN** a query exactly matches an authorized client's normalized email or full name and also matches documents
- **THEN** the exact client identity match receives its defined identity precedence before generally fused results

#### Scenario: Embedding runtime is unavailable
- **WHEN** client lexical retrieval and document lexical retrieval succeed but query embedding is unavailable
- **THEN** the response retains both authorized result types, identifies `lexical_degraded` mode, and applies the lexical mixed-ranking policy

#### Scenario: Same mixed query is repeated
- **WHEN** the authorized data, active profile, ranking version, query, and page inputs are unchanged
- **THEN** the ordered typed result identities and cursor boundaries are unchanged
