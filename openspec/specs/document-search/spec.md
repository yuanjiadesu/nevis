# document-search Specification

## Purpose

Provide auditable, tenant-isolated document discovery that combines lexical and semantic evidence without allowing unauthorized records to enter candidate ranking or result construction.

## Requirements

### Requirement: Predictable field-specific lexical matching
The system SHALL apply punctuation-aware token matching to client emails, token-prefix matching
to client identity fields and document titles, and whole-term full-text matching to document
content. Exact normalized client email and full-name matches SHALL retain precedence over general
lexical matches. When a field family yields no lexical candidate, the system SHALL apply bounded
trigram similarity matching to client full names and document titles only, above an explicit
similarity floor. It SHALL NOT apply trigram or other approximate matching to client email,
client description, or document content.

#### Scenario: Email domain query
- **WHEN** an authorized advisor searches `nevis.test`
- **THEN** clients whose email domain is `nevis.test` are eligible general client results even
  though the submitted query contains punctuation

#### Scenario: Partial client identity query
- **WHEN** an authorized advisor submits a token prefix of a client name or email
- **THEN** that client is eligible as a general client result

#### Scenario: Partial document title query
- **WHEN** an authorized advisor submits a token prefix found in a current document title
- **THEN** that document is eligible with lexical evidence

#### Scenario: Partial document content query
- **WHEN** a token prefix occurs only in document content and has no whole-term or semantic match
- **THEN** that prefix alone does not make the document eligible with lexical evidence

#### Scenario: Misspelled client name query
- **WHEN** a query is a near miss of an authorized client's full name and no exact, prefix, or
  full-text client evidence exists
- **THEN** that client is eligible as a trigram client result above the similarity floor

#### Scenario: Misspelled document title query
- **WHEN** a query is a near miss of a current document title and no document lexical evidence
  exists
- **THEN** that document is eligible as a trigram document result above the similarity floor

#### Scenario: Lexical evidence already exists
- **WHEN** exact, prefix, or full-text evidence exists for a field family
- **THEN** trigram matching contributes no candidate for that family and the returned records are
  unchanged

#### Scenario: Document content evidence suppresses title fallback
- **WHEN** document lexical retrieval finds whole-term content evidence but no title evidence
- **THEN** the document-title trigram fallback does not run

#### Scenario: Misspelled content term
- **WHEN** a query is a near miss of a term that occurs only in document content
- **THEN** that document is not eligible through trigram matching and remains eligible only
  through whole-term or semantic evidence

#### Scenario: Query is below the similarity floor
- **WHEN** no authorized client full name or document title reaches the declared trigram
  similarity floor
- **THEN** trigram matching contributes no candidate and the query returns no approximate record

#### Scenario: Near miss of a complete identifier
- **WHEN** a query is a complete email address or domain that differs from an authorized client's
  identifier
- **THEN** the literal identifier route runs without trigram matching and returns no approximate
  client

### Requirement: Typed match boundaries
The system SHALL return client and document matches as independent typed results. A client match
SHALL NOT by itself make documents owned by that client eligible for the mixed result list.

#### Scenario: Only client identity matches
- **WHEN** a query matches a client identity but none of that client's documents has qualifying
  title, content, or semantic evidence
- **THEN** the client may be returned and its documents are not added solely because of ownership

### Requirement: Evidence-first mixed search
The system SHALL use one versioned evidence-first policy to route queries, gather authorized
candidates, rank document evidence, and return a bounded source-grounded preview. Every executed
stage SHALL retain the existing tenant, lifecycle, current-version, and active-profile
constraints.

#### Scenario: Email or domain query
- **WHEN** an authorized advisor searches with a recognized email address or domain identifier
- **THEN** the system searches client identity fields and literal document text without admitting
  documents solely because their meaning is close to the identifier

#### Scenario: Document contains the literal identifier
- **WHEN** an email or domain query literally matches indexed document text
- **THEN** the matching document remains eligible through lexical retrieval

#### Scenario: Natural-language evidence query
- **WHEN** an authorized advisor searches for `address proof` and a current document describes a
  utility bill that evidences the client's residential address
- **THEN** the system gathers lexical and vector candidates, ranks their supporting passages
  against the query, and places that evidence ahead of an address-change note that says evidence
  was not supplied and an investment note about utility companies

#### Scenario: Winning evidence occurs later in a document
- **WHEN** the strongest lexical or semantic evidence is beyond the beginning of a current
  document
- **THEN** the document result contains a bounded plain-text excerpt from that supporting passage
  rather than a generated statement or the unrelated document opening

#### Scenario: Nonsense query
- **WHEN** a query has no labelled lexical or semantic relevance in the authorized corpus
- **THEN** final relevance admission returns no arbitrary nearest document

#### Scenario: Final evidence ranking is unavailable
- **WHEN** authorized lexical and vector candidate retrieval succeeds but the configured evidence
  ranker is unavailable or times out
- **THEN** the system returns the bounded hybrid candidates with an explicit
  `hybrid_unreranked` mode and does not present their ordering as reranked evidence

#### Scenario: Client result is returned
- **WHEN** a search result represents a client rather than a document
- **THEN** document evidence ranking and preview construction do not alter that client's identity
  precedence or expose document content through the client result

### Requirement: Authorization precedes candidate retrieval
The system SHALL require an allowed tenant-scoped advisor authorization decision for mixed search and SHALL constrain client lexical, client trigram, document lexical, document title trigram, and document semantic candidate sets to that tenant before scoring, ranking, aggregation, merging, counting, or result construction.

#### Scenario: Authorized tenant search
- **WHEN** an advisor with an active membership submits a valid search for a tenant
- **THEN** every client and document candidate considered by the search belongs to that tenant

#### Scenario: Missing or inactive membership
- **WHEN** a protected search has no valid advisor context or the advisor lacks an active membership in the asserted tenant
- **THEN** the system returns no client or document result, count, score, snippet, or provenance data and records a denied decision

#### Scenario: Matching content exists in another tenant
- **WHEN** an authorized advisor searches their tenant and a stronger matching client or document exists only in another tenant
- **THEN** the other tenant's record does not affect candidate sets, ordering, pagination, or response metadata

#### Scenario: Trigram match exists in another tenant
- **WHEN** a misspelled query is a near miss of a client or document title that exists only in another tenant
- **THEN** that record contributes no trigram candidate and the searching tenant receives no approximate result

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
The system SHALL make every client result attributable to its tenant, client, creation authorization decision, and search authorization decision, and every document result attributable to its tenant, client, source, document, current document version, embedding profile, indexing authorization decision, and search authorization decision. Every document result SHALL also carry its owning client's display name so the result is readable without a further request. It SHALL persist a credential-safe mixed-search audit record without raw query text, snippets, client PII, document content, vectors, or provider credentials.

#### Scenario: Search result is returned
- **WHEN** client and document results are included in one response
- **THEN** each result's discriminator and provenance identify its required type-specific lineage and the common search authorization decision

#### Scenario: Document result identifies its client
- **WHEN** a search returns a document result
- **THEN** the result carries its owning client's identity and display name, and no document result is returned without one

#### Scenario: Search completes
- **WHEN** an allowed search succeeds in hybrid, lexical-degraded, or empty-result mode
- **THEN** the audit trail records a query fingerprint, typed result identities, mixed-ranking version, retrieval mode, bounded score metadata, result count, and latency without recording raw customer content

### Requirement: Deterministic mixed client and document ranking
The system SHALL combine independently ranked authorized client and document candidates into one deterministic list without comparing raw lexical, semantic, and trigram scores directly. Exact client identity matches SHALL receive their defined precedence, trigram and corrected-query candidates SHALL occupy the lowest match band beneath all general candidates, and candidates SHALL use a versioned rank-fusion policy with stable type and identity tie-breakers.

#### Scenario: Client and document matches coexist
- **WHEN** a query has authorized client and current-document matches
- **THEN** the response contains both result types in one total order produced by the declared mixed-ranking version

#### Scenario: Exact client identity match coexists with document evidence
- **WHEN** a query exactly matches an authorized client's normalized email or full name and also matches documents
- **THEN** the exact client identity match receives its defined identity precedence before fused results

#### Scenario: Approximate candidate coexists with general evidence
- **WHEN** one fallback returns approximate candidates and another field family returns general lexical or semantic candidates
- **THEN** every general candidate precedes every approximate candidate in the returned order

#### Scenario: Trigram candidates are ordered among themselves
- **WHEN** several trigram candidates clear the similarity floor
- **THEN** their branch positions are combined by the declared fixed rank-fusion policy with stable result-type and record-identity tie-breakers

#### Scenario: Corrected semantic candidate coexists with a trigram candidate
- **WHEN** the bounded spelling retry and a trigram fallback both contribute approximate candidates
- **THEN** all approximate branches are combined by the declared fixed rank-fusion policy with stable result-type and record-identity tie-breakers

#### Scenario: Fuzzy title has unrelated content
- **WHEN** a document title reaches the similarity floor but its leading content does not pass content reranker admission
- **THEN** the document remains eligible in the fuzzy match band

#### Scenario: Embedding runtime is unavailable
- **WHEN** client lexical retrieval and document lexical retrieval succeed but query embedding is unavailable
- **THEN** the response retains both authorized result types, identifies `lexical_degraded` mode, and applies the lexical mixed-ranking policy

#### Scenario: Same mixed query is repeated
- **WHEN** the authorized data, active profile, ranking version, query, and page inputs are unchanged
- **THEN** the ordered typed result identities and cursor boundaries are unchanged

### Requirement: Empty-result semantic spelling recovery
When an ordinary non-identifier search produces no admitted exact or general result, the system SHALL attempt at most one deterministic local correction of one eligible final query token and SHALL retry document retrieval once when an eligible correction exists. A correction SHALL be eligible only for an alphabetic final token of at least five characters with one unique dictionary candidate at edit distance one. Results admitted only by the retry SHALL occupy the fuzzy match band. The system SHALL retain the submitted query for client matching, display, cursor binding, authorization, audit, and telemetry, and SHALL NOT disclose or record the corrected text.

#### Scenario: Final semantic term is one character short
- **WHEN** `investment opportunit` has no admitted ordinary result and `opportunity` is its unique eligible correction
- **THEN** document retrieval is retried once with `investment opportunity` and any admitted results appear in the fuzzy match band

#### Scenario: Ordinary search succeeds
- **WHEN** the submitted query produces an admitted exact or general result
- **THEN** spelling correction and corrected document retrieval do not run

#### Scenario: Final token is ineligible or ambiguous
- **WHEN** an empty ordinary search has no eligible unique one-edit correction for its final token
- **THEN** no corrected retrieval runs and spelling recovery contributes no result

#### Scenario: Complete identifier is misspelled
- **WHEN** a complete email address or domain produces no literal result
- **THEN** spelling correction and corrected document retrieval do not run

#### Scenario: Corrected retrieval remains tenant scoped
- **WHEN** corrected document evidence exists only in another tenant
- **THEN** it does not affect candidates, ranking, pagination, or response metadata

### Requirement: Active embedding profile consistency
The system SHALL embed a query and select semantic candidates using one immutable active embedding profile, and SHALL exclude vectors produced by every other profile from that semantic ranking.

#### Scenario: Multiple embedding profiles exist
- **WHEN** indexed chunks exist for active and inactive embedding profiles
- **THEN** semantic retrieval ranks only vectors associated with the profile used to embed the query

### Requirement: Preserve field-specific document admission
The system SHALL record whether title, content, or semantic evidence admitted each document. Exact and prefix title matches SHALL survive content-reranker rejection. Content-only and semantic-only candidates SHALL still pass final admission.

#### Scenario: Exact title is absent from content
- **WHEN** an exact current title matches but its content fails reranking
- **THEN** the document remains a general result

#### Scenario: Title prefix is absent from content
- **WHEN** a current title prefix matches but its content fails reranking
- **THEN** the document remains a general result

#### Scenario: Content-only candidate fails
- **WHEN** a candidate has no title match and fails final admission
- **THEN** it is not returned

#### Scenario: Title and passage both match
- **WHEN** one document has title and passage evidence
- **THEN** the system returns one deterministic result with its best admitted passage

#### Scenario: Search is degraded
- **WHEN** embedding or reranking fails but title retrieval succeeds
- **THEN** the title match remains eligible under the degraded policy
