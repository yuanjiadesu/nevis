## Why

The platform enforces tenant membership but currently accepts the advisor identity from a request header, so it cannot safely expose protected APIs outside a trusted local environment. The master plan identifies a small single-issuer OIDC boundary as the remaining production identity requirement without expanding into a general identity or policy platform.

## What Changes

- Add a provider-neutral advisor identity contract with an OIDC bearer-token implementation for production and deterministic header/injected implementations for local development and automated tests.
- Verify production access-token signature, asymmetric algorithm, issuer, audience, expiry, and subject against one configured OIDC issuer, with bounded cached signing-key refresh for routine key rotation.
- Map the verified OIDC subject to the existing advisor external identity, then continue using the existing database-backed active tenant membership policy.
- Keep tenant selection explicit through the existing tenant header; do not infer authorization from token roles, organizations, or other claims.
- **BREAKING**: production protected APIs no longer accept `X-Nevis-Advisor` as an identity source. That header remains available only in explicitly configured local/test modes.
- Return credential-safe `401` responses for absent or invalid identity, `403` for an authenticated advisor who is not an active member, and `503` when identity verification is temporarily impossible.
- Fail production configuration closed when OIDC or signing configuration is incomplete, unsafe, or combined with a non-production identity provider.
- Preserve authorization-decision and audit lineage using safe identity mode and issuer metadata without storing bearer tokens or raw claims.

## Capabilities

### New Capabilities

- `advisor-identity`: Authenticates an advisor through a production OIDC access token or an explicitly non-production identity provider and produces a credential-safe identity for authorization.

### Modified Capabilities

- `tenant-advisor-authorization`: Requires authenticated advisor identity before tenant membership evaluation and records safe identity context with each authorization decision.
- `platform-runtime`: Separates local/test and production identity modes and refuses readiness for unsafe production identity configuration or unavailable verification keys.

## Impact

- Affects protected ingestion, document-version status, and search dependencies and their `401`/`403`/`503` contracts.
- Adds a small JWT/JOSE verification dependency and uses the existing HTTP client for OIDC discovery/JWKS retrieval; no identity orchestration framework is introduced.
- Uses `advisors.external_id` as the single-issuer OIDC `sub` mapping, with no schema migration required for this increment.
- Adds settings, cached JWKS lifecycle, safe authentication telemetry, local signing-key fixtures, API tests, and production/local documentation.
- Does not add token issuance, passwords, SAML, SCIM, multi-issuer federation, claim-based tenant roles, a custom policy engine, clients, mixed search, or new observability infrastructure.
