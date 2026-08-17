# platform-runtime Specification

## Purpose

Provide a reproducible local runtime for the Nevis API platform and its required infrastructure before product capabilities are introduced.

## Requirements

### Requirement: Reproducible local platform startup
The system SHALL start the API service, worker service, PostgreSQL database with vector-search support, and local embedding runtime from the repository's documented Compose command without requiring a hosted-provider credential.

#### Scenario: Developer starts the local platform
- **WHEN** a developer follows the documented local startup command with the required container runtime installed
- **THEN** all required services start from version-pinned configuration and the API is reachable locally

### Requirement: Service health reporting
The system SHALL expose separate liveness and readiness endpoints that report whether the API process is running and whether the dependencies required by its configured environment are usable. Production readiness SHALL include the ability to verify identity using configured or valid cached issuer keys.

#### Scenario: Dependencies are ready
- **WHEN** the database, active embedding runtime, and all dependencies required by the configured identity mode are usable
- **THEN** the readiness endpoint returns a successful response

#### Scenario: A required dependency is unavailable
- **WHEN** the database, active embedding runtime, or production identity verifier has no usable verification keys
- **THEN** the readiness endpoint returns a non-success response identifying the unavailable dependency without exposing credentials or sensitive configuration

#### Scenario: Local identity mode is ready
- **WHEN** the platform runs in local mode with valid local identity configuration and its existing database and embedding dependencies are usable
- **THEN** readiness succeeds without requiring an external OIDC service

### Requirement: Fail-closed production identity configuration
The system SHALL distinguish local, test, and production environments and SHALL refuse production readiness when the OIDC issuer, audience, asymmetric algorithm allowlist, signing-key configuration, or identity provider is missing, internally inconsistent, unsafe, or configured with documented local/test defaults.

#### Scenario: Production identity configuration is valid
- **WHEN** the platform starts in production with complete non-placeholder single-issuer OIDC settings and a production identity provider
- **THEN** identity configuration validation succeeds before readiness can be reported

#### Scenario: Production identity configuration is unsafe
- **WHEN** production selects local-header or deterministic identity, lacks required OIDC settings, permits a symmetric or unsupported token algorithm, or uses documented placeholder values
- **THEN** the platform refuses readiness with credential-safe configuration diagnostics

### Requirement: Verified development quality gates
The system SHALL provide documented commands and continuous-integration checks for formatting, static type checking, automated tests, and unapplied database migrations.

#### Scenario: A proposed change violates a quality gate
- **WHEN** a change fails formatting, type checking, tests, or migration validation
- **THEN** continuous integration reports the failed check and does not report the quality suite as successful

### Requirement: Same-origin advisor console delivery
The system SHALL serve the compiled advisor console and its static assets from the API origin in local and fictional-data user acceptance testing (UAT) environments, without a separate frontend runtime service and without a Node runtime in the application image.

#### Scenario: Platform origin is opened in a browser
- **WHEN** a user opens the platform origin in a browser
- **THEN** the compiled console is returned and calls the documented API paths on that same origin

#### Scenario: Static console asset is requested
- **WHEN** the browser requests a compiled console asset
- **THEN** the API returns it without intercepting health or protected API routes

#### Scenario: Container image is built
- **WHEN** the production API image is built from the repository
- **THEN** it contains the compiled console assets and requires no Node runtime at application execution time

### Requirement: Enforce summary-worker parity
When summaries are enabled, the API SHALL require a fresh worker heartbeat with matching non-secret enabled state, provider, model, and prompt identity. Disabled deployments SHALL not require a summary provider or heartbeat.

#### Scenario: Configuration matches
- **WHEN** a fresh worker heartbeat matches the API
- **THEN** summary delivery is ready

#### Scenario: Worker is missing
- **WHEN** the API enables summaries but the worker heartbeat is missing or stale
- **THEN** readiness fails with a safe diagnostic

#### Scenario: Configuration differs
- **WHEN** API and worker summary identities differ
- **THEN** readiness fails without exposing sensitive data

#### Scenario: Summaries are disabled
- **WHEN** summaries are consistently disabled
- **THEN** normal readiness needs no summary provider or heartbeat

### Requirement: Report summary diagnostics
An operator diagnostic SHALL report bounded current-version state counts, safe failure counts, and heartbeat freshness. It SHALL omit documents, clients, summaries, prompts, provider responses, endpoints, and credentials.

#### Scenario: Operator checks delivery
- **WHEN** the diagnostic runs
- **THEN** it distinguishes disabled, missing, delayed, and failed delivery

#### Scenario: Output is produced
- **WHEN** the diagnostic returns data
- **THEN** it contains no sensitive content

### Requirement: Verify the UAT pipeline
The fictional-data user acceptance testing (UAT) environment SHALL provide a bounded check that ingests or revises a document, waits for indexing and summary work, verifies exact-title search, and verifies a ready labelled summary.

#### Scenario: Pipeline is healthy
- **WHEN** dependencies and API-worker configuration are valid
- **THEN** the version is indexed, searchable by an unrelated exact title, and reaches `ready`

#### Scenario: Pipeline fails
- **WHEN** any stage fails
- **THEN** the check reports the stage safely and does not report success
