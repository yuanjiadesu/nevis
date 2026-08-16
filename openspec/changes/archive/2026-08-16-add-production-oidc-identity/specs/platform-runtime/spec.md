## ADDED Requirements

### Requirement: Fail-closed production identity configuration
The system SHALL distinguish local, test, and production environments and SHALL refuse production readiness when the OIDC issuer, audience, asymmetric algorithm allowlist, signing-key configuration, or identity provider is missing, internally inconsistent, unsafe, or configured with documented local/test defaults.

#### Scenario: Production identity configuration is valid
- **WHEN** the platform starts in production with complete non-placeholder single-issuer OIDC settings and a production identity provider
- **THEN** identity configuration validation succeeds before readiness can be reported

#### Scenario: Production identity configuration is unsafe
- **WHEN** production selects local-header or deterministic identity, lacks required OIDC settings, permits a symmetric or unsupported token algorithm, or uses documented placeholder values
- **THEN** the platform refuses readiness with credential-safe configuration diagnostics

## MODIFIED Requirements

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
