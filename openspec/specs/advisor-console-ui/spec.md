# advisor-console-ui Specification

## Purpose
Provide advisors with one compact browser console for finding client information and managing client and document records through the platform's existing authorized contracts.

## Requirements

### Requirement: Single-destination console shell
The console SHALL present a persistent shell containing the Nevis wordmark, active workspace identity, adviser identity and global search, with the client directory and the record opened from it as the only content destination. The shell SHALL use product-scale typography and density and SHALL serve every brand asset, font, and control locally.

#### Scenario: Advisor opens the console
- **WHEN** an authenticated advisor opens the console
- **THEN** the shell displays the workspace identity and search while client and document content changes beneath it, without a navigation rail listing a single destination

#### Scenario: Public marketing site is unavailable
- **WHEN** the console loads while `neviswealth.com` or its CDN is unreachable
- **THEN** the wordmark, fonts, and layout render without requesting any public-site asset

#### Scenario: Advisor uses a narrow viewport
- **WHEN** the viewport cannot display the full content columns
- **THEN** every control remains reachable through compact treatments and collections restyle to stacked rows without horizontal page scrolling

### Requirement: Global client and document search
The console SHALL provide a globally reachable search surface backed by the existing authorized mixed-search contract. It SHALL distinguish client and document results, present only the fields the API returns, and expose loading, empty, degraded, and error states.

#### Scenario: Advisor submits a query
- **WHEN** the advisor submits a valid query from the global search surface
- **THEN** the console shows authorized client and document matches labelled by result type and identifies lexical-degraded retrieval when the API reports it

#### Scenario: Advisor opens a result
- **WHEN** the advisor activates a client result, or a document result that has a client association
- **THEN** the search surface closes and the corresponding client record becomes the selected content, with the matched document openable from that context

#### Scenario: Result has no client association
- **WHEN** a returned document result carries no client association
- **THEN** the console presents it as an identifiable but non-navigable legacy record and fabricates no client route

#### Scenario: Search cannot return results
- **WHEN** the query is invalid, the request fails, or no authorized matches exist
- **THEN** the console presents the API's safe error or an explicit empty state and shows no stale results as current matches

#### Scenario: Advisor invokes search from the keyboard
- **WHEN** the advisor presses the documented shortcut outside an editable field
- **THEN** the search surface opens with focus in its labelled input, results are reachable by keyboard, and dismissing it returns focus to the invoking control

### Requirement: Client directory and record management
The console SHALL present a bounded, tenant-authorized client directory and a client record view with safe fields, and SHALL provide focused create and edit interactions that report only API-confirmed outcomes.

#### Scenario: Advisor opens the directory
- **WHEN** an authenticated advisor opens the console
- **THEN** the directory shows the authorized clients as a paginated collection with its loading, empty, and failure states as applicable

#### Scenario: Advisor changes client details
- **WHEN** the advisor submits valid editable client fields
- **THEN** the console reports the API result and refreshes every affected view without inventing local success data

### Requirement: Document collection and contextual actions
A client record SHALL present its documents as one structured collection with a result count, a filter control scoped to loaded rows, one primary add-document action, and per-row title, current version, creation date, and indexing status. Secondary document operations SHALL collapse into a keyboard-accessible row action menu.

#### Scenario: Advisor filters loaded documents
- **WHEN** the advisor types in the document collection filter
- **THEN** visible rows narrow to case-insensitive title matches, the collection reports the filtered count or an explicit no-match state, and it labels the filter as covering loaded rows when further pages exist

#### Scenario: Advisor uses a document row
- **WHEN** the advisor activates a document title, or opens its row action menu
- **THEN** the title opens current content, and the menu offers editing and version history without shifting other row content

#### Scenario: Advisor opens version history
- **WHEN** the advisor selects version history
- **THEN** the console presents ordered versions with number, creation time, indexing status, and a control to view each immutable version's content

#### Scenario: Advisor submits document intake
- **WHEN** the advisor submits valid plain-text document fields for the selected client
- **THEN** the console shows the accepted version and its returned indexing state, refreshes the timeline, and never represents indexing as complete before the API reports it

#### Scenario: Client has no documents
- **WHEN** the selected client has no document records
- **THEN** the collection shows one compact empty state carrying the add-document action

### Requirement: Bounded console footprint
The console SHALL remain a deliberately small operational surface. A runtime UI dependency SHALL supply behavior rather than visual identity, and the console SHALL NOT adopt a component framework whose stylesheet ships independently of what is rendered. The compiled footprint SHALL stay within the budget recorded in the change tasks.

#### Scenario: Console is built
- **WHEN** the production console build runs
- **THEN** its compiled stylesheet and script stay within the recorded budget and include no component-framework global stylesheet

#### Scenario: A UI dependency is proposed
- **WHEN** a new runtime UI dependency is considered
- **THEN** it is adopted only if it supplies behavior the console would otherwise implement by hand, and its visual output remains governed by the project's own tokens

### Requirement: Accessible operational presentation
Navigation, search, collections, menus, dialogs, forms, and status indicators SHALL be operable by keyboard and understandable to assistive technology, with labelled controls, visible focus, live async feedback, and status conveyed by more than color alone.

#### Scenario: Async state changes after an advisor action
- **WHEN** search or record data changes in response to an advisor action
- **THEN** the visible state and an appropriate live region communicate the outcome without moving keyboard focus unexpectedly
