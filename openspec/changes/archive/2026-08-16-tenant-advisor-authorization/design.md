## Context

The platform currently stores a single `organizations` owner on document lineage and records a fixed `global-policy-v1 / allow` value. Ingestion and document-version status endpoints do not identify a caller, and the worker copies the global decision onto jobs and chunks. See [proposal.md](proposal.md) and the delta specifications for the behavioral contract.

## Goals / Non-Goals

**Goals:**

- Establish a normalized tenant/advisor/membership model and preserve existing UUID-based lineage through the upgrade.
- Make ingestion and document-version status tenant-authorized, consistently audited, and safe against cross-tenant existence disclosure.
- Persist a first-class immutable authorization decision and attach its identity to newly indexed provenance.
- Supply a composable SQL authorization predicate for the retrieval change that follows this one.

**Non-Goals:**

- User login, session management, API keys, SSO/OIDC integration, or a tenant-administration API.
- Fine-grained client, household, document classification, role permissions, delegated access, or policy editing.
- Implementing vector search, ranking, result rendering, or generation.

## Decisions

### Preserve identifiers while replacing the global owner with a tenant

Create a `tenants` relation and migrate the existing `organizations` rows to it without changing their UUIDs; rename dependent ownership columns from `organization_id` to `tenant_id` and rebuild affected uniqueness constraints. The `nevis-global` row becomes the initial tenant. This gives database-level tenant ownership a precise name while retaining every existing document/source/version/chunk/audit identity.

Creating an unrelated tenant row and keeping `organization_id` as an alias was considered. It would create two ownership concepts and make an omitted join too easy during later retrieval, so it is rejected.

### Store authorization decisions separately from audit events

Add immutable `authorization_decisions` with tenant, advisor (nullable only for the one-time migration decision), action, policy identifier/version, result, request ID, and credential-safe context. Each decision emission also creates the corresponding append-only audit event. Protected data stores its authoritative ingestion decision UUID, not merely copied policy/result strings; jobs and chunks inherit that UUID. Historical indexed data is backfilled to one immutable migration decision that records its prior global allow context.

Using only the existing audit event as a foreign-key target was considered. A dedicated decision record supports authorization lineage without overloading audit-event semantics or relying on metadata parsing.

### Use an upstream-authenticated principal adapter, not an identity provider

Introduce a request dependency that accepts a tenant slug and advisor UUID asserted by the trusted upstream authentication gateway, resolves the active membership, evaluates the policy, and returns an authorization context. Until an identity-provider change is made, local development/tests will supply these assertions through documented request headers; production deployment must only accept them after a trusted gateway has authenticated and stripped client-supplied versions. Missing, invalid, or inactive identities are denied and audited where a tenant can be resolved.

Adding in-app passwords or OAuth in this change was considered and rejected because it would entangle the data boundary with a separately evolving identity lifecycle. Trusting arbitrary public headers without a gateway is also rejected as insecure.

### Authorize before loading protected records

Ingestion authorizes the resolved tenant before it writes an idempotency record, source, document, version, or job. Document-version status first evaluates the caller context, then adds `tenant_id` to the lookup predicate; absence and cross-tenant access return the same not-found response. The future retrieval repository will receive an already-authorized context and must compose its tenant predicate into the candidate query before vector distance, ordering, limit, count, or result projection.

Filtering results after a vector query was considered and rejected because rank, timing, count, and metadata can leak cross-tenant information.

### Keep authorization policy intentionally simple and provision memberships out of band

The initial policy allows an active membership to perform `document.ingest` and `document-version.read` only for its tenant. Tenant and advisor records/memberships are provisioned through migration fixtures and an operator-controlled database/bootstrap procedure; management APIs come later. The policy identifier is versioned (for example, `tenant-membership-v1`) to make decisions attributable as rules evolve.

Building roles now was considered but deferred: a single membership policy validates the boundary without prematurely freezing an advisor-permission model.

## Risks / Trade-offs

- [A direct deployment could accept forged development identity headers] → Require the gateway trust boundary in deployment documentation, bind the service privately, and add gateway/IdP integration before Internet exposure.
- [Column/table renames can lock or fail on production-sized data] → Use an additive/backfill/validate/constraint-swap migration sequence, test upgrade and downgrade on the Compose database, and schedule a maintenance window for the constraint swap.
- [Historical data lacks an advisor identity] → Use one explicit migration authorization decision with a null advisor and preserve the original immutable audit records rather than inventing a human actor.
- [Membership status changes while work is queued] → Indexing retains the decision that authorized ingestion; future retrieval evaluates a fresh caller decision and does not infer access from the historical ingestion decision.
- [A forgotten tenant predicate in a later query leaks data] → Centralize the predicate in the authorization repository, make retrieval acceptance tests use two tenants, and require every returned result to expose its provenance references internally.

## Migration Plan

1. Deploy code that can read the new tenant and authorization relations behind the migration, while keeping the service in maintenance mode.
2. Add tenant/advisor/membership/decision tables; migrate `organizations` to `tenants`, preserve UUIDs, rename ownership columns, and rebuild foreign keys and uniqueness constraints.
3. Backfill one immutable migration decision for existing allowed data, attach it to document versions/jobs/chunks, and preserve historical audit events unchanged except for their migrated tenant foreign key.
4. Ensure `nevis-global` exists exactly once, provision a test/operator advisor membership, then enable the protected endpoint dependency and worker propagation.
5. Verify migration upgrade/downgrade, two-tenant isolation, allowed/denied audit trails, and retry behavior before enabling any retrieval change.

Rollback is code-first: if the new authorization dependency must be disabled before a destructive schema phase, retain the migrated tenant schema and restrict the service to maintenance rather than reintroducing global allow. Downgrade is supported only before production membership data is created; after real tenant data exists, restore from a tested backup or use a forward corrective migration.
