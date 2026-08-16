## Purpose

Provide a reproducible local runtime for the Nevis API platform and its required infrastructure before product capabilities are introduced.

## ADDED Requirements

### Requirement: Reproducible local platform startup
The system SHALL start the API service, worker service, PostgreSQL database with vector-search support, and local embedding runtime from the repository's documented Compose command without requiring a hosted-provider credential.

#### Scenario: Developer starts the local platform
- **WHEN** a developer follows the documented local startup command with the required container runtime installed
- **THEN** all required services start from version-pinned configuration and the API is reachable locally

### Requirement: Service health reporting
The system SHALL expose separate liveness and readiness endpoints that report whether the API process is running and whether its required startup dependencies are usable.

#### Scenario: Dependencies are ready
- **WHEN** the database and active embedding runtime are usable
- **THEN** the readiness endpoint returns a successful response

#### Scenario: A required dependency is unavailable
- **WHEN** the database or active embedding runtime cannot be reached
- **THEN** the readiness endpoint returns a non-success response identifying the unavailable dependency without exposing credentials or sensitive configuration

### Requirement: Verified development quality gates
The system SHALL provide documented commands and continuous-integration checks for formatting, static type checking, automated tests, and unapplied database migrations.

#### Scenario: A proposed change violates a quality gate
- **WHEN** a change fails formatting, type checking, tests, or migration validation
- **THEN** continuous integration reports the failed check and does not report the quality suite as successful
