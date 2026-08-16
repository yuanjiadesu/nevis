## Purpose

Provide auditable, tenant-isolated document discovery that combines lexical and semantic evidence without allowing unauthorized records to enter candidate ranking or result construction.

## ADDED Requirements

### Requirement: Authorization precedes candidate retrieval
The system SHALL require an allowed tenant-scoped advisor authorization decision for document search and SHALL constrain both lexical and semantic candidate sets to that tenant before scoring, ranking, aggregation, or result construction.

#### Scenario: Authorized tenant search
- **WHEN** an advisor with an active membership submits a valid search for a tenant
- **THEN** every lexical and semantic candidate considered by the search belongs to that tenant

#### Scenario: Missing or inactive membership
- **WHEN** a protected search has no valid advisor context or the advisor lacks an active membership in the asserted tenant
- **THEN** the system returns no document result, count, score, snippet, or provenance data and records a denied decision

#### Scenario: Matching content exists in another tenant
- **WHEN** an authorized advisor searches their tenant and a stronger matching document exists only in another tenant
- **THEN** the other tenant's document does not affect the candidate set, ordering, pagination, or response

### Requirement: Hybrid document retrieval
The system SHALL retrieve lexical and semantic evidence from successfully indexed current document versions, combine the independent candidate ranks deterministically, and aggregate supporting chunks into document-level results.

#### Scenario: Query has lexical and semantic evidence
- **WHEN** a valid query matches indexed current-version chunks through lexical and semantic retrieval
- **THEN** the response returns documents ordered by a deterministic fused rank with a best supporting snippet and component score metadata

#### Scenario: Historical version matches more strongly
- **WHEN** a historical document version matches but a newer successfully indexed version is current
- **THEN** default search considers only the current successfully indexed version

#### Scenario: No candidate clears retrieval thresholds
- **WHEN** a query produces no sufficiently relevant lexical or semantic candidate
- **THEN** the system returns an empty successful result set rather than arbitrary nearest neighbours

### Requirement: Explicit degraded retrieval mode
The system SHALL continue with lexical retrieval when query embedding is unavailable, SHALL identify the response as `lexical_degraded`, and SHALL fail closed when authorization or database access is unavailable.

#### Scenario: Embedding runtime is unavailable
- **WHEN** authorization and the database are available but the configured embedding runtime cannot embed the query
- **THEN** the search returns tenant-scoped lexical results with mode `lexical_degraded` and records the dependency degradation

#### Scenario: Database access is unavailable
- **WHEN** the search cannot obtain its authorized candidates from the database
- **THEN** the request fails with a credential-safe service error and returns no partial result set

### Requirement: Stable bounded search contract
The system SHALL validate normalized query text and page size, return an opaque cursor for additional results, and apply a total deterministic order using fused rank and stable record identity.

#### Scenario: First page has more results
- **WHEN** a valid search has more authorized results than the requested bounded page size
- **THEN** the response includes an opaque next cursor that continues the same query, tenant, embedding profile, and retrieval mode after the final returned result

#### Scenario: Cursor context is invalid
- **WHEN** a cursor is malformed, modified, expired, or belongs to another query, tenant, profile, or retrieval mode
- **THEN** the system rejects it without revealing search results or internal cursor state

#### Scenario: Query is invalid
- **WHEN** normalized query text is empty or exceeds the documented bound, or the requested limit is outside its allowed range
- **THEN** the system returns a validation error without executing retrieval

### Requirement: Result and audit provenance
The system SHALL make every returned result attributable to its tenant, source, document, current document version, embedding profile, originating indexing authorization decision, and the authorization decision governing the search. It SHALL persist a credential-safe search audit record without raw query text, snippets, document content, vectors, email addresses, or provider credentials.

#### Scenario: Search result is returned
- **WHEN** a document is included in a search response
- **THEN** its result provenance and the persisted search audit data can identify all required lineage records and the search authorization decision

#### Scenario: Search completes
- **WHEN** an allowed search succeeds in hybrid, lexical-only, or empty-result mode
- **THEN** the audit trail records a query fingerprint, returned document identities, ranking mode, bounded score metadata, result count, and latency without recording raw customer content

### Requirement: Active embedding profile consistency
The system SHALL embed a query and select semantic candidates using one immutable active embedding profile, and SHALL exclude vectors produced by every other profile from that semantic ranking.

#### Scenario: Multiple embedding profiles exist
- **WHEN** indexed chunks exist for active and inactive embedding profiles
- **THEN** semantic retrieval ranks only vectors associated with the profile used to embed the query

