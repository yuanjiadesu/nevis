## Context

The repository currently contains the assignment materials and the approved production-platform plan. This change establishes only the runtime and durable boundaries that later ingestion and search capabilities will use; see `proposal.md` for motivation and the change specs for externally observable requirements.

## Goals / Non-Goals

**Goals:**

- Create a repeatable local and CI development baseline.
- Establish a single PostgreSQL source of truth for domain metadata, audit lineage, migrations, and future vector retrieval.
- Make local embeddings the default while keeping hosted providers optional and isolated behind a domain-owned contract.
- Make readiness, migration state, and quality checks observable from the first commit.

**Non-Goals:**

- Client/document APIs, document chunking, background indexing jobs, and any search endpoint.
- Authentication, roles, tenancy policy enforcement, or a full event-sourcing system.
- Hosted-provider adapters, Langfuse deployment, Kubernetes deployment, or production secrets management.

## Decisions

### FastAPI application and worker processes

Use a FastAPI application factory with a separately invokable worker process. FastAPI provides typed OpenAPI HTTP boundaries; a separate worker keeps durable asynchronous work out of request handlers when indexing is introduced.

**Alternatives considered:** A monolithic process with framework background tasks is simpler initially but cannot provide durable job execution or independent scaling. Django is unnecessary because the initial product is an API/service platform rather than a server-rendered application.

### `uv`-managed Python project

Use Python 3.12, `pyproject.toml`, and committed `uv.lock`. CI uses locked dependency installation. This gives cross-machine repeatability without hand-managed requirements files.

**Alternatives considered:** Poetry and pip-tools are viable, but `uv` is selected for a single fast project workflow and a committed universal lockfile.

### PostgreSQL, pgvector, SQLAlchemy async, and Alembic

Use PostgreSQL 16 with pgvector as the initial persistence service. SQLAlchemy 2 async with `asyncpg` provides the application persistence boundary; Alembic is the only mechanism that changes the schema. The first migration creates `organizations`, `audit_events`, and `embedding_profiles` and seeds `nevis-global` idempotently.

**Alternatives considered:** Splitting a vector database from relational storage would add operational complexity before retrieval exists. `create_all` is unsuitable because schema history and deployment state must be reviewable.

### Local TEI default and provider adapter boundary

Define an `EmbeddingProvider` application contract for document embedding, query embedding, and health checks. Implement only `LocalTEIProvider` in this change. The active `EmbeddingProfile` is persisted and records provider, model, revision, dimensions, normalization, chunking version, and pipeline version.

The selected TEI image and model revision are fixed in Compose configuration. A deterministic fake provider exists for tests but is not a runtime profile.

**Alternatives considered:** A hosted provider as default would be quicker but prevents a credential-free reproducible demo. Direct SDK calls would make later provider switching and provenance difficult.

### Global authorization and audit boundary

Seed one organization and centralize `global-policy-v1 / allow` decision construction in an authorization-context component. Persist append-only audit events through the application transaction boundary. The audit store is not a full event-sourcing system; it records traceable security and operational facts.

**Alternatives considered:** Omitting organization and decision fields until multi-tenancy would require later backfills and weaken result provenance. Building RBAC now would contradict the agreed global scope.

### Operational surface and CI

Expose `/health/live` for process liveness and `/health/ready` for database and provider readiness. CI runs formatting, linting, type checks, unit tests, integration tests against PostgreSQL/pgvector, and Alembic upgrade/check validation. Logs and telemetry use IDs, hashes, counts, and dependency status; they do not emit raw document content, emails, or provider credentials.

## Risks / Trade-offs

- [Local model/image increases download and startup cost] → Pin model/image versions, document cache requirements, and keep hosted providers optional.
- [Readiness depends on TEI even before indexing exists] → Require only a lightweight provider health endpoint; liveness remains independent.
- [PostgreSQL durable-job design is deferred] → Do not introduce worker business jobs in this change; Phase 2 defines transactional job semantics explicitly.
- [A single global organization could be mistaken for tenant isolation] → Document `global-policy-v1` clearly and require future retrieval specs to add organization filtering before enabling multi-tenancy.
- [Audit records can grow indefinitely] → Store minimal structured metadata now; define retention and archival in a later compliance change.

## Migration Plan

1. Build application and service images from locked dependencies.
2. Start PostgreSQL and TEI, then run Alembic migrations as an explicit startup/deployment step.
3. Seed `nevis-global` idempotently within the initial migration or bootstrap command.
4. Start API and worker services only after required dependencies are ready.
5. Verify liveness, readiness, migration head, and quality suite.

Rollback consists of stopping the new services and restoring the prior application image. The initial schema migration is additive; a downgrade script is supplied for local recovery before any production data is introduced.

## Open Questions

- The exact local TEI image/model pair and CPU resource budget will be selected during implementation from compatible, pinned artifacts; it does not change the provider contract or first-release behavior.
