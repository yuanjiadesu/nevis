## Why

Nevis needs a production-grade, reproducible foundation before client ingestion and AI search can be added safely. Establishing the runtime, data-lineage boundary, provider contract, and quality gates now prevents later search features from coupling directly to a particular embedding vendor or losing auditable provenance.

## What Changes

- Create a Python 3.12 FastAPI service and worker foundation managed by `uv`.
- Provide a reproducible Docker Compose development stack with PostgreSQL, pgvector, and a local Text Embeddings Inference (TEI) service as the default embedding runtime.
- Establish SQLAlchemy 2 async persistence, Alembic migrations, and a seeded global organization named `nevis-global`.
- Establish an append-only audit-event baseline that records the global authorization decision context; the release remains globally searchable and adds no authentication or RBAC.
- Define a provider-neutral embedding contract, immutable embedding-profile metadata, and a local TEI implementation without adding document indexing or search behavior.
- Add health/readiness checks, formatting, type checking, tests, CI quality gates, and developer documentation.

## Capabilities

### New Capabilities

- `platform-runtime`: Run the API, worker, database, and local embedding runtime reproducibly with observable liveness and readiness.
- `global-data-lineage`: Establish the single global organization and append-only audit foundation required to attribute later retrieval results.
- `embedding-provider-runtime`: Select, identify, and check the health of a provider-neutral embedding runtime without coupling the platform to a hosted vendor.

### Modified Capabilities

- None.

## Impact

- Adds the initial Python application structure, `pyproject.toml`/`uv.lock`, Dockerfiles, Compose configuration, and CI workflow.
- Adds PostgreSQL with pgvector and a pinned local TEI image/model configuration to local development.
- Adds database migrations and the initial schema for organizations, audit events, and embedding profiles.
- Does not add client/document endpoints, indexing jobs, document chunks, semantic retrieval, or search APIs; those are later changes.
