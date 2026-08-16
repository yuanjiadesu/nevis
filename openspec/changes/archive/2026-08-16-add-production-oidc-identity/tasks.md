## 1. Identity contract and configuration

- [x] 1.1 Add closed environment and identity-provider settings plus bounded OIDC issuer, audience, algorithm, token length, clock-skew, key-cache, refresh, timeout, and stale-window settings.
- [x] 1.2 Add fail-closed settings validation for the local/test/production provider matrix, HTTPS production issuer, required audience, asymmetric algorithms, and non-placeholder production secrets.
- [x] 1.3 Add the selected JWT/JOSE cryptographic dependency, lock it with `uv`, and verify its license and dependency audit.
- [x] 1.4 Define transport-neutral identity credentials, authenticated identity, provider protocol, readiness result, and credential-safe invalid/unavailable error types in the domain boundary.

## 2. Non-production identity providers

- [x] 2.1 Implement local-header identity for local mode with bounded advisor identifiers and generic missing/invalid identity errors.
- [x] 2.2 Implement a deterministic injected identity provider for unit and integration tests without network access or credentials.
- [x] 2.3 Add unit tests proving local/test identity works only in its allowed environment and production rejects every non-production provider combination.

## 3. Production OIDC provider

- [x] 3.1 Implement OIDC discovery with exact issuer matching, HTTPS JWKS URL validation, bounded HTTP timeouts, response-size limits, and credential-safe errors.
- [x] 3.2 Implement in-memory parsed-JWKS caching with fresh/max-stale bounds, a single-flight refresh lock, and rate-limited unknown-`kid` refresh.
- [x] 3.3 Implement bearer-token verification for scheme/length, asymmetric algorithm, `kid`, signature, issuer, audience, expiry, bounded subject, and optional `nbf`.
- [x] 3.4 Implement provider readiness, initial key warm-up, cached-key outage behavior, and async HTTP-client shutdown.
- [x] 3.5 Add deterministic asymmetric key, discovery, JWKS, token, controllable-clock, and HTTP transport fixtures.
- [x] 3.6 Add unit tests for valid tokens, every invalid claim/signature/algorithm case, ignored authorization claims, concurrent refresh, rotation, stale boundaries, malformed-token refresh suppression, issuer outage, and complete credential redaction.

## 4. Authentication and authorization integration

- [x] 4.1 Add an identity-provider factory and install the selected provider in the FastAPI lifespan without changing the default local Compose path.
- [x] 4.2 Replace route-level advisor extraction with one shared dependency that authenticates first, keeps `X-Nevis-Tenant` explicit, and passes the verified external identity to membership authorization.
- [x] 4.3 Map missing/invalid identity to generic `401` with a bearer challenge, verification unavailability to `503`, and mapped-advisor/membership denial to the existing generic `403`.
- [x] 4.4 Pass safe identity mode and issuer identifiers into authorization-decision context and audit metadata without storing subject claims, tokens, keys, or authorization headers.
- [x] 4.5 Verify production `X-Nevis-Advisor` values cannot override bearer identity while retaining the documented header flow only in local mode.
- [x] 4.6 Add PostgreSQL-backed API tests across ingestion, version status, and search for valid identity, unknown advisor, inactive membership, missing/unknown tenant, cross-tenant attempts, token role/tenant claims, header spoofing, decision lineage, and unchanged local behavior.

## 5. Readiness, documentation, and release verification

- [x] 5.1 Extend production readiness with OIDC verification-key usability while keeping liveness and local readiness independent of the external issuer.
- [x] 5.2 Add `.env.example`, Compose, README, API, and runbook guidance for local identity, production OIDC configuration, advisor `sub` provisioning, key rotation/outage, ingress migration, and rollback requirements.
- [x] 5.3 Add safe authentication outcome logging and assertions that tokens, claims, signing material, authorization headers, and advisor external subjects never reach telemetry or API errors.
- [x] 5.4 Run formatting, linting, strict typing, unit/integration/contract suites, migration checks, Compose validation, real-TEI smoke, dependency audit, and strict OpenSpec validation.
- [x] 5.5 Verify a production-mode smoke flow against the deterministic OIDC service fixture, including key rotation, issuer outage with cached keys, fail-closed stale expiry, authorization-before-retrieval, and complete result provenance.
