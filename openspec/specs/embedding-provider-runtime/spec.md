# embedding-provider-runtime Specification

## Purpose

Provide a provider-neutral embedding runtime boundary so later indexing and search can be traced to an immutable embedding profile and deployed locally by default.

## Requirements

### Requirement: Active embedding profile identity
The system SHALL persist an active embedding profile with provider, model, model revision when available, vector dimension, normalization, chunking version, and pipeline version.

#### Scenario: The platform identifies the active runtime
- **WHEN** a service requests the active embedding configuration
- **THEN** it receives the complete immutable profile identity required to attribute later vectors and retrieval results

### Requirement: Provider-neutral embedding operations
The system SHALL expose document and query embedding operations through a provider-neutral application contract.

#### Scenario: A provider is selected by configuration
- **WHEN** a supported embedding provider is configured as active
- **THEN** application callers use the same document and query embedding contract without provider-specific behavior in their interface

### Requirement: Local embedding default
The system SHALL select a local TEI-compatible embedding provider as the default development profile and SHALL not require a hosted-provider API key for local readiness.

#### Scenario: Default local configuration is used
- **WHEN** the platform starts without a hosted embedding-provider configuration
- **THEN** it uses the configured local embedding runtime and reports its availability through readiness checks

### Requirement: Embedding runtime failure reporting
The system SHALL report an embedding-provider health failure as a dependency failure without exposing provider credentials or input content.

#### Scenario: Embedding runtime is unavailable
- **WHEN** the active embedding runtime cannot answer a health check
- **THEN** the platform reports the provider as unavailable through its readiness and operational telemetry surfaces
