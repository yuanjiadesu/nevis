## Purpose

Authenticate the advisor behind each protected request through a minimal provider-neutral boundary that supports verified single-issuer OIDC identity in production and deterministic identity only in explicitly non-production environments.

## ADDED Requirements

### Requirement: Environment-bound identity provider
The system SHALL select an identity provider from the configured runtime environment and SHALL permit local-header or deterministic injected identity only in local or test environments.

#### Scenario: Local identity is explicitly configured
- **WHEN** the platform runs in local mode and a protected request supplies the documented local advisor identity
- **THEN** the system produces an authenticated local identity for the existing tenant authorization path without contacting an OIDC issuer

#### Scenario: Test identity is injected
- **WHEN** an automated test runs in test mode with a deterministic identity provider
- **THEN** the system can exercise authentication and authorization without network access or production credentials

#### Scenario: Non-production identity is selected in production
- **WHEN** production configuration selects local-header, deterministic, fake, or otherwise non-production identity
- **THEN** the platform refuses to become ready

### Requirement: Verified production OIDC identity
The system SHALL authenticate a production request only from a bearer access token whose asymmetric signing algorithm, signature, issuer, audience, expiry, and non-empty subject are valid for one configured OIDC issuer. It SHALL use the verified subject as the advisor external identity and SHALL NOT derive tenant membership from token claims.

#### Scenario: Valid access token
- **WHEN** a protected production request presents a valid access token from the configured issuer for the configured audience
- **THEN** the system returns an authenticated identity containing the verified subject and production identity mode for tenant authorization

#### Scenario: Access token is absent or invalid
- **WHEN** a protected production request has no bearer token or its algorithm, signature, issuer, audience, expiry, or subject is invalid
- **THEN** the system returns a generic `401` response before tenant authorization or protected data access

#### Scenario: Token contains tenant or role claims
- **WHEN** a valid token contains tenant, organization, role, group, or permission claims
- **THEN** those claims do not grant tenant membership or alter the database-backed authorization result

### Requirement: Signing-key rotation and bounded availability
The system SHALL cache verified issuer signing keys for a bounded period, SHALL perform one bounded refresh when a validly formed token references an unknown key identifier, and SHALL fail closed when no usable verification key is available.

#### Scenario: Issuer rotates its signing key
- **WHEN** a token references a new key identifier published by the configured issuer
- **THEN** the system refreshes signing keys within its bounded policy and can verify the token without a process restart

#### Scenario: Issuer is temporarily unavailable with a usable cached key
- **WHEN** signing-key refresh is unavailable but the token can be verified with an unexpired cached key
- **THEN** authentication continues using the cached key until its configured validity boundary

#### Scenario: Verification keys are unavailable
- **WHEN** the token cannot be verified because no usable cached key exists and the issuer key endpoint is unavailable
- **THEN** the system returns a credential-safe `503` response and exposes no protected data

### Requirement: Credential-safe identity handling
The system SHALL NOT persist or emit bearer tokens, raw JWT claims, signing keys, or authorization-header values in logs, audit events, metrics, traces, errors, or API responses.

#### Scenario: Authentication succeeds or fails
- **WHEN** the system records an authentication outcome
- **THEN** operational metadata is limited to safe outcome categories, identity mode, request correlation, and a non-sensitive issuer identifier

