## MODIFIED Requirements

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

## ADDED Requirements

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
