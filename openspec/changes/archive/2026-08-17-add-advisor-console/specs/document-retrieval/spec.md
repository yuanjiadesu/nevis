## ADDED Requirements

### Requirement: List a client’s documents

The system SHALL return a bounded, stable document page for an authorised same-tenant client. It SHALL include safe current-version state and an opaque cursor without content.

#### Scenario: Adviser requests a document page

- **WHEN** an adviser with active membership requests a client’s document page
- **THEN** the system returns only that client’s documents, current state, and a cursor when needed

#### Scenario: Client is absent or cross-tenant

- **WHEN** an adviser requests an unknown or cross-tenant client
- **THEN** the system returns the same `404` without document metadata

### Requirement: List document versions

The system SHALL return an authorised document’s immutable version history without content. Unknown and cross-tenant documents SHALL share the same `404`.

#### Scenario: Adviser requests version history

- **WHEN** an adviser with active membership requests an authorised document’s history
- **THEN** the system returns each version’s identity, number, creation time, and indexing state in stable order
