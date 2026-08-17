## Purpose

Describe an immutable document version without making generated text part of search or document availability.

## ADDED Requirements

### Requirement: Generate summaries asynchronously

When generation is enabled, the system SHALL create at most one summary record per document version. It SHALL generate from that version’s complete normalized content. Generation SHALL NOT block ingestion, indexing, retrieval, or search.

#### Scenario: Accept a new version

- **WHEN** ingestion records a non-empty document version while generation is enabled
- **THEN** it creates pending summary work in the same transaction without calling OpenCode

#### Scenario: Enable generation after ingestion

- **WHEN** generation is enabled after document versions already exist
- **THEN** the system creates no retroactive summary work

#### Scenario: Revise a document

- **WHEN** a summarized document receives a new version
- **THEN** the old summary remains with its version and the new version returns `null` until generation completes

#### Scenario: Exhaust retries

- **WHEN** generation reaches its retry limit
- **THEN** the summary fails safely and the document remains indexed, searchable, and retrievable

#### Scenario: Recover a lease

- **WHEN** a worker stops during generation
- **THEN** another worker can recover the work after lease expiry without creating a duplicate

### Requirement: Bound OpenCode generation

The system SHALL call the configured OpenCode Chat Completions model with deterministic sampling and `store: false`. The prompt SHALL permit only facts stated in the document. The system SHALL store no more than two plain-text sentences within the configured output bound. It SHALL not submit empty, partial, or oversized content.

#### Scenario: Summarize valid content

- **WHEN** complete normalized content fits the input bound
- **THEN** the system submits it and stores only normalized output within the sentence and size limits

#### Scenario: Reject empty or oversized content

- **WHEN** normalized content is empty or exceeds the input bound
- **THEN** the system makes no provider call and exposes no summary

#### Scenario: Reject invalid output

- **WHEN** OpenCode returns empty, malformed, or oversized output
- **THEN** the system stores no summary and records a safe failure

### Requirement: Protect the API boundary

The system SHALL enable OpenCode only for deployments marked for fictional test data. It SHALL require `OPENCODE_API_KEY` as the only provider secret and inject provider identity, model, and endpoint through validated deployment settings. The endpoint SHALL use HTTPS, SHALL target `opencode.ai`, and SHALL use a Chat Completions path. It SHALL NOT persist or expose the key.

Each record SHALL identify its provider, model, and prompt version. Logs and audit records SHALL NOT contain document content, submitted content, prompts, summaries, or credentials.

#### Scenario: Reject a non-test deployment

- **WHEN** a deployment without the fictional-test-data setting enables OpenCode
- **THEN** startup fails before submitting document content

#### Scenario: Reject a missing key

- **WHEN** OpenCode is enabled without `OPENCODE_API_KEY`
- **THEN** startup fails before submitting document content

#### Scenario: Reject an unsafe endpoint

- **WHEN** OpenCode is enabled with a non-HTTPS, non-OpenCode, credential-bearing, query-bearing, fragment-bearing, or non-Chat-Completions endpoint
- **THEN** startup fails before submitting document content

#### Scenario: Call OpenCode

- **WHEN** the worker summarizes fictional test data
- **THEN** it calls the validated configured endpoint with the configured model, secret bearer credential, and `store: false`

#### Scenario: Record an outcome

- **WHEN** generation completes or fails
- **THEN** the record keeps the version, provider, model, prompt version, outcome, and safe failure code

#### Scenario: Run automated tests

- **WHEN** tests generate a summary
- **THEN** a deterministic fake returns bounded output without a network call or credential

### Requirement: Keep generated text display-only

The system SHALL treat summaries as sensitive, untrusted display text. It SHALL NOT use them for chunking, embedding, retrieval, matching, ranking, routing, authorization, or search results. The console SHALL label displayed summaries as AI-generated.

#### Scenario: Ignore document instructions

- **WHEN** document content attempts to direct the model or platform
- **THEN** escaped summary text cannot change search or authorization behavior

#### Scenario: Display a ready summary

- **WHEN** an authorized adviser views a document with a ready current-version summary
- **THEN** the console shows the summary, its label, and a path to the source document

#### Scenario: Omit an absent summary

- **WHEN** the current version has no ready summary
- **THEN** the console omits it without an error or delay
