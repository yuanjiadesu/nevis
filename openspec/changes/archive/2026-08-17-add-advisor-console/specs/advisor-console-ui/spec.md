## Purpose

Give advisers one browser console for finding clients and managing client documents through authorised APIs.

## ADDED Requirements

### Requirement: Show one console destination

The console SHALL show the Nevis wordmark, workspace, adviser, and global search in a persistent shell. The client directory and selected record SHALL form the only destination. All brand assets and fonts SHALL load locally.

#### Scenario: Adviser opens the console

- **WHEN** an authenticated adviser opens the console
- **THEN** the shell shows workspace identity and search without a one-item navigation rail

#### Scenario: Public site is unavailable

- **WHEN** `neviswealth.com` or its content delivery network is unavailable
- **THEN** the console renders without requesting a public-site asset

#### Scenario: Adviser uses a narrow viewport

- **WHEN** the viewport cannot fit all columns
- **THEN** controls remain reachable and collections become stacked rows without horizontal page scrolling

### Requirement: Search clients and documents

The console SHALL expose the authorised mixed-search contract globally. It SHALL distinguish client and document results and show loading, empty, degraded, and error states.

#### Scenario: Adviser submits a query

- **WHEN** an adviser submits a valid global query
- **THEN** the console shows authorised typed results and reports `lexical_degraded` when returned

#### Scenario: Adviser opens a result

- **WHEN** an adviser opens a client result or an associated document result
- **THEN** search closes and the matching client context opens

#### Scenario: Result has no client

- **WHEN** a document result has no client association
- **THEN** the console shows a non-navigable legacy result without creating a client route

#### Scenario: Search has no result

- **WHEN** a query is invalid, fails, or has no authorised match
- **THEN** the console shows the safe error or empty state without stale matches

#### Scenario: Adviser uses the keyboard shortcut

- **WHEN** an adviser presses the shortcut outside an editable field
- **THEN** search opens with input focus, supports keyboard results, and restores focus when dismissed

### Requirement: Manage client records

The console SHALL show a bounded, tenant-authorised client directory and client record. Create and edit actions SHALL report only API-confirmed outcomes.

#### Scenario: Adviser opens the directory

- **WHEN** an authenticated adviser opens the console
- **THEN** the directory shows paginated authorised clients and the applicable request state

#### Scenario: Adviser updates a client

- **WHEN** an adviser submits valid editable fields
- **THEN** the console reports the API result and refreshes affected views

### Requirement: Manage a client’s documents

A client record SHALL show a document collection with count, loaded-row filter, primary add action, current version, creation date, indexing status, and keyboard-accessible row actions.

#### Scenario: Adviser filters documents

- **WHEN** an adviser enters a title filter
- **THEN** loaded rows filter case-insensitively and the console reports count, no-match state, and limited scope

#### Scenario: Adviser uses a document row

- **WHEN** an adviser opens a title or row menu
- **THEN** the title opens content and the menu offers editing and version history

#### Scenario: Adviser opens version history

- **WHEN** an adviser selects version history
- **THEN** the console shows ordered version identity, time, status, and content controls

#### Scenario: Adviser adds a document

- **WHEN** an adviser submits valid plain-text document fields
- **THEN** the console shows the accepted version and API-reported indexing state

#### Scenario: Client has no documents

- **WHEN** the selected client has no documents
- **THEN** the collection shows one empty state with the add action

### Requirement: Bound the console footprint

Runtime interface dependencies SHALL supply behavior, not visual identity. The console SHALL stay within the recorded CSS and JavaScript budgets.

#### Scenario: Console is built

- **WHEN** the production build runs
- **THEN** CSS and JavaScript stay within budget without a component-framework stylesheet

#### Scenario: Interface dependency is proposed

- **WHEN** a runtime dependency is considered
- **THEN** it is accepted only for needed behavior governed by project styling

### Requirement: Keep the console accessible

Navigation, search, collections, menus, dialogs, forms, and statuses SHALL support keyboard and assistive technology. Controls SHALL have labels, visible focus, live feedback, and non-color status cues.

#### Scenario: Async state changes

- **WHEN** an adviser action changes search or record data
- **THEN** the visible state and live region report the outcome without unexpected focus movement
