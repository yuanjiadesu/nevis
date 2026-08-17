## ADDED Requirements

### Requirement: Return summary availability
Safe document resources and client timelines SHALL return `summary_status` and nullable `summary`. Only `ready` SHALL include summary text. State SHALL not affect authorization, ordering, or pagination.

#### Scenario: Summary is ready
- **WHEN** an authorized adviser retrieves a ready summary
- **THEN** the response returns `summary_status: ready` and bounded text

#### Scenario: Summary was not requested
- **WHEN** no summary row exists
- **THEN** the response returns `summary_status: not_requested` and `summary: null`

#### Scenario: Summary is active
- **WHEN** work is queued or processing
- **THEN** the response returns its state and `summary: null` without delay

#### Scenario: Summary failed
- **WHEN** summary work failed
- **THEN** the response returns `summary_status: failed` and `summary: null` without provider details

#### Scenario: Timeline has mixed states
- **WHEN** timeline rows have different summary states
- **THEN** each row reports its state without changing order or cursors

#### Scenario: Console shows state
- **WHEN** a document appears in the console
- **THEN** ready text is labelled AI-generated and absent text has a concise state label

