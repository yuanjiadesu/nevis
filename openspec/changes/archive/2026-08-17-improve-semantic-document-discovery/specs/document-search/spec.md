## ADDED Requirements

### Requirement: Match lexical fields predictably

The system SHALL use punctuation-aware matching for client emails, token prefixes for client identity and document titles, and whole terms for document content. Exact normalized email and full-name matches SHALL keep higher precedence.

#### Scenario: Adviser searches an email domain

- **WHEN** an authorised adviser searches `nevis.test`
- **THEN** clients with that email domain are eligible despite punctuation

#### Scenario: Adviser searches a client prefix

- **WHEN** an authorised adviser enters a token prefix from a client name or email
- **THEN** the client is eligible as a general result

#### Scenario: Adviser searches a title prefix

- **WHEN** an authorised adviser enters a token prefix from a current document title
- **THEN** the document is eligible with lexical evidence

#### Scenario: Prefix occurs only in content

- **WHEN** a prefix has no whole-term or semantic content match
- **THEN** the prefix alone does not admit the document

### Requirement: Keep result types independent

The system SHALL return client and document matches as separate typed results. A client match SHALL NOT admit documents through ownership alone.

#### Scenario: Only client identity matches

- **WHEN** a query matches a client but none of its documents has qualifying evidence
- **THEN** the client can appear without its documents

### Requirement: Rank source evidence

The system SHALL use one versioned policy to route queries, retrieve authorised candidates, rank document passages, and return a bounded source preview. Every stage SHALL enforce tenant, lifecycle, current-version, and active-profile constraints.

#### Scenario: Adviser searches an email or domain

- **WHEN** an authorised adviser enters a recognised email or domain
- **THEN** search uses client identity and literal document text without semantic identifier matches

#### Scenario: Document contains the identifier

- **WHEN** document text contains the submitted email or domain
- **THEN** the document remains eligible through lexical retrieval

#### Scenario: Adviser searches for address evidence

- **WHEN** an authorised adviser searches `address proof` and a utility bill supports the address
- **THEN** the utility bill ranks above address-change text that denies evidence and investment text about utilities

#### Scenario: Best evidence occurs later

- **WHEN** the strongest evidence appears after the document opening
- **THEN** the result returns a bounded excerpt from that passage

#### Scenario: Adviser enters nonsense

- **WHEN** no authorised evidence is relevant
- **THEN** final admission returns no arbitrary nearest document

#### Scenario: Evidence ranking fails

- **WHEN** authorised candidate retrieval succeeds but the ranker fails or times out
- **THEN** the system returns bounded candidates with `hybrid_unreranked`

#### Scenario: Search returns a client

- **WHEN** a result represents a client
- **THEN** document ranking does not change client precedence or expose document content
