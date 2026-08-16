## 1. Project and developer foundation

- [x] 1.1 Initialize the Python 3.12 `uv` project with locked runtime, development, and test dependencies.
- [x] 1.2 Create the modular `src/nevis` application, domain, infrastructure, worker, and test package layout.
- [x] 1.3 Add typed settings loading, a `.env.example`, and safe defaults that do not contain credentials.
- [x] 1.4 Add Ruff formatting/linting, mypy configuration, pytest configuration, and documented local commands.
- [x] 1.5 Add the application factory and separate worker entry point without business routes or job execution.

## 2. Reproducible local runtime

- [x] 2.1 Select a compatible TEI image and embedding model revision, pin both in repository configuration, and document CPU/resource expectations.
- [x] 2.2 Create Dockerfiles for the API and worker using locked Python dependencies.
- [x] 2.3 Create Compose configuration for API, worker, PostgreSQL with pgvector, and the local TEI service without hosted-provider credentials.
- [x] 2.4 Add startup ordering and dependency health checks so service readiness is evaluated after required dependencies are reachable.
- [x] 2.5 Document one-command local startup, shutdown, reset, and dependency-cache troubleshooting.

## 3. Persistence and lineage baseline

- [x] 3.1 Configure async SQLAlchemy and Alembic against PostgreSQL with pgvector enabled.
- [x] 3.2 Define organization, audit-event, and embedding-profile persistence models with explicit constraints and timestamps.
- [x] 3.3 Create the initial Alembic upgrade and downgrade migration, including idempotent seeding of exactly one `nevis-global` organization.
- [x] 3.4 Implement the global authorization-context component that produces `global-policy-v1 / allow` decisions.
- [x] 3.5 Implement append-only audit-event persistence and prohibit application update/delete operations for audit records.
- [x] 3.6 Add integration tests for migration upgrade/downgrade, single-organization seeding, audit persistence, and append-only behavior.

## 4. Embedding runtime boundary

- [x] 4.1 Define the provider-neutral embedding contract for document embedding, query embedding, and health checks.
- [x] 4.2 Implement immutable embedding-profile creation and active-profile retrieval with complete provenance metadata.
- [x] 4.3 Implement `LocalTEIProvider` using the configured local TEI endpoint and map dependency failures to safe operational errors.
- [x] 4.4 Implement a deterministic fake provider for tests without registering it as a production runtime profile.
- [x] 4.5 Add tests proving callers use the provider-neutral contract and local startup does not require hosted-provider credentials.

## 5. Health, telemetry, and quality gates

- [x] 5.1 Implement `/health/live` and `/health/ready` with dependency-specific, credential-safe readiness reporting.
- [x] 5.2 Add structured logging and telemetry helpers that exclude document content, email addresses, query text, and provider credentials.
- [x] 5.3 Add unit and integration tests for ready and unavailable database/embedding-runtime states.
- [x] 5.4 Add CI jobs that run locked dependency verification, format/lint, type checks, tests, and Alembic migration validation.
- [x] 5.5 Add an end-to-end Compose smoke test that verifies the API, worker, database, TEI runtime, and readiness endpoint.

## 6. Documentation and change validation

- [x] 6.1 Update the README with architecture summary, prerequisites, local startup, quality commands, and scope boundaries.
- [x] 6.2 Add an operational runbook covering health failures, migration troubleshooting, and safe local-reset guidance.
- [x] 6.3 Verify the OpenSpec change with strict validation and resolve every reported issue.
- [x] 6.4 Confirm the implementation remains limited to the foundation: no client/document APIs, indexing workflow, or search endpoint.
