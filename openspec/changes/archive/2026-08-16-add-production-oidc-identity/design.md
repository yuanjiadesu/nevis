## Context

See `proposal.md` for motivation. Protected routes currently receive `X-Nevis-Tenant` and `X-Nevis-Advisor`, resolve both in PostgreSQL, persist an authorization decision, and authorize only active memberships. Tenant filtering and result lineage are already correct; only the origin of the advisor external identity is unverified.

The existing `authorization_decisions.context` JSON can retain safe identity metadata, so this change does not require a database migration. The application already uses `httpx`, Pydantic settings, FastAPI lifespan dependencies, structured logging, and separate liveness/readiness checks.

## Goals / Non-Goals

**Goals:**

- Authenticate production callers through one OIDC issuer without changing the membership policy.
- Keep identity transport and JWT mechanics outside the authorization domain.
- Handle signing-key rotation and short issuer outages without a network call per request.
- Fail closed with stable, credential-safe HTTP and readiness behavior.
- Preserve deterministic, network-free local development and tests.

**Non-Goals:**

- Token issuance, interactive login, refresh tokens, browser sessions, logout, passwords, or operating an identity provider.
- Multiple issuers, SAML, SCIM, social identity, account linking, or issuer-qualified advisor records.
- Reading tenant membership, roles, groups, or permissions from token claims.
- A custom policy engine, new authorization roles, client records, mixed search, or observability infrastructure.
- Persisting tokens, full claims, signing keys, or an authentication-event database.

## Decisions

### 1. Separate authentication from authorization

Add a domain-level `IdentityProvider` protocol that receives transport-neutral credentials and returns an immutable `AuthenticatedIdentity` containing only `external_id`, identity mode, and a safe issuer identifier. It also exposes a small readiness operation and async close lifecycle.

Implement three adapters:

- `LocalHeaderIdentityProvider` for `local` mode;
- `DeterministicIdentityProvider` for tests; and
- `OIDCIdentityProvider` for `production`.

The FastAPI dependency extracts the bearer token, local advisor header, tenant header, and request correlation ID. It authenticates first, then passes the returned external identity and explicit tenant to the existing authorization use case. Authorization remains responsible for tenant/advisor lookup, active membership, decision persistence, and audit.

Alternative considered: make the authorization use case parse JWTs. Rejected because token verification and membership policy change for different reasons and require different tests.

### 2. Use a closed environment/provider matrix

Settings use closed values rather than arbitrary strings:

| Environment | Allowed identity provider |
|---|---|
| `local` | `local-header` |
| `test` | deterministic injected provider |
| `production` | `oidc` |

Production requires a non-placeholder cursor key, HTTPS OIDC issuer, expected audience, and an allowlist containing only supported asymmetric algorithms. The initial default algorithm is `RS256`; support for another asymmetric algorithm is added only with verification tests. Local Compose behavior remains unchanged.

Alternative considered: infer production from whether OIDC variables happen to exist. Rejected because partial configuration can silently select an unsafe path.

### 3. Use OIDC discovery plus local JWT verification

The production adapter loads the issuer's discovery document, requires its returned issuer to match configuration exactly, and accepts only an HTTPS `jwks_uri`. A small JOSE/JWT library verifies access tokens locally. Validation requires:

- a bearer scheme and bounded token length;
- an allowlisted asymmetric `alg` and a present `kid`;
- a matching signature key;
- exact issuer and configured audience;
- unexpired `exp`, honoring only a small bounded clock skew;
- a non-empty bounded `sub`; and
- `nbf` validation when present.

Other claims are ignored for authorization. The verified `sub` maps directly to the existing `advisors.external_id`, which is sufficient because the master plan supports one issuer.

Alternative considered: token introspection or user-info calls on every request. Rejected because signed access tokens can be verified locally and per-request issuer calls add latency and availability coupling.

### 4. Cache signing keys with a bounded stale window

Keep discovery metadata and parsed signing keys in process memory. Configuration defines a fresh TTL and a longer bounded maximum-stale TTL. Within the fresh TTL no network request occurs. On an unknown `kid`, one rate-limited, single-flight refresh occurs even if the cache is fresh. If refresh fails, a known key may remain usable only until maximum stale age; afterward readiness and protected authentication fail closed.

The provider warms discovery/JWKS during lifespan startup or the first readiness check and closes its `httpx.AsyncClient` on shutdown. It never persists public keys to the application database.

Alternative considered: refresh keys for every request. Rejected for latency and issuer load. Alternative considered: trust cached keys forever during outage. Rejected because removed keys need a bounded retirement path.

### 5. Keep failure classes explicit and responses generic

Identity adapters distinguish:

- missing/invalid credentials → `401` with a generic bearer challenge;
- verification dependency unavailable → `503`; and
- successful identity whose advisor mapping or membership fails → existing generic `403`.

Malformed tokens do not trigger repeated network refreshes. Unknown `kid` refresh is bounded and rate-limited. An unauthenticated request does not create an authorization decision because it has no trustworthy advisor context; it emits only a PII-safe correlated operational event. After authentication, existing allow/deny authorization decisions remain authoritative.

### 6. Reuse existing decision context instead of changing schema

Pass `identity_mode` and a safe normalized issuer identifier into `create_authorization_decision(..., context=...)` and the authorization audit metadata. Store neither the subject nor token claims in this extra context; the durable advisor foreign key already identifies the mapped subject for allowed/known-advisor decisions.

For a verified but unknown advisor, resolve the explicit tenant first and create the existing denied decision with `advisor_id = NULL`, safe identity mode, and issuer metadata. Unknown tenants cannot produce the current tenant-foreign-key decision and are rejected without protected data.

### 7. Test OIDC deterministically without a real provider

Generate ephemeral asymmetric test keys, tokens, discovery documents, and JWKS fixtures. Inject `httpx.MockTransport` and a controllable clock into the provider. Unit tests cover claims, algorithms, cache boundaries, refresh single-flight, key rotation, stale-key behavior, and redaction. API integration tests run production settings against the deterministic OIDC fixture and continue to use the real PostgreSQL authorization path.

No hosted identity service or network credential is required in CI.

## Risks / Trade-offs

- **[Issuer outage after process restart prevents readiness]** → Production fails closed; existing processes can use bounded cached keys, and operators see the identity dependency as unavailable.
- **[Using `advisors.external_id = sub` couples records to one issuer]** → This is explicit in the master plan; introduce `(issuer, subject)` identity links before adding a second issuer.
- **[JWKS refresh can be abused with random key identifiers]** → Validate token shape and algorithm first, allow only one rate-limited single-flight refresh, and never fetch caller-controlled URLs.
- **[A removed signing key remains accepted during the stale window]** → Keep the stale window bounded and configurable; emergency key compromise requires issuer and application cache invalidation/restart procedures.
- **[Production header clients break]** → The change is intentionally breaking only in production; update ingress and clients to send bearer tokens before enabling production mode.
- **[Readiness depends on OIDC keys]** → This accurately represents whether a fresh process can authenticate; liveness remains independent.

## Migration Plan

1. Add the identity contract, error types, settings, and local/test adapters while retaining local mode as the default.
2. Add the OIDC adapter, deterministic key fixtures, cache/rotation tests, and readiness integration.
3. Route all protected endpoints through identity before the existing authorization use case and add safe identity decision context.
4. Provision each production advisor so `external_id` exactly matches the configured issuer's stable `sub`.
5. Configure and verify OIDC in a non-production deployment, including invalid tokens, membership denial, key rotation, issuer outage, and header-spoof attempts.
6. Update ingress and API clients to send bearer tokens, then enable `production`/`oidc` together.

Rollback to the previous release is safe only behind a trusted private gateway that restores validated advisor-header injection. No database rollback is needed; new JSON context fields remain backward-compatible and are retained for audit history.
