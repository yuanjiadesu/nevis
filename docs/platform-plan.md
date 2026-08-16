# Platform plan

**Status:** the mixed-search platform is implemented and verified. Operations and recovery
are the next milestone.

This document sets program direction. OpenSpec defines bounded feature changes; it does not
redefine the quality bar. Update this plan first when scope, architecture, or acceptance
criteria change.

## Outcome and workload

Build a secure, tenant-aware search platform for wealth-management client records and
documents. The initial workload assumes about 10,000 clients, 10–100 English plain-text
documents per client, documents around 10 KB, and a short acceptable indexing delay. Search
returns one client/document result list without maintained keyword or synonym maps.

Quality means secure identity, tenant-isolated access, durable and attributable data,
reproducible behaviour, observable failures, tested recovery, and measured fitness for this
workload. It does not require maximum infrastructure complexity.

## Quality bar

| Area | Required evidence |
| --- | --- |
| Identity | Verify one OIDC issuer locally; map its subject to an advisor. |
| Authorisation | Check database membership and filter by tenant before retrieval; record every decision. |
| Data integrity | Keep immutable versions, idempotent writes, migrations, and complete result lineage. |
| Reproducibility | Lock dependencies and version model, profile, chunking, ranking, thresholds, and fixtures. |
| Verification | Pass code, database, API, relevance, security, and performance gates. |
| Operations | Provide readiness, PII-safe logs and metrics, degraded modes, safe shutdown, and retry behaviour. |
| Recovery | Rehearse backup/restore, application rollback, migration, embedding recovery, and indexing replay. |
| Capacity | Meet the targets below with representative data or record a time-bounded accepted risk. |

Current targets:

- p95 write acknowledgement below 300 ms, excluding asynchronous indexing.
- p95 indexed search below 800 ms at expected load.
- p95 indexing lag below five minutes.
- No unaudited protected search or write outcome.

The current architecture meets the representative search target at 100,000 documents. A
broad-match case remains a time-bounded risk; see the
[measured envelope](architecture.md#measured-envelope).

## Boundaries

The modular monolith fits the declared workload: FastAPI, PostgreSQL/pgvector, a durable
database worker, and a configured embedding provider. Add infrastructure only when a
measured or regulatory requirement cannot be met safely within that design.

The implementation includes:

- Tenant-owned clients and client-associated immutable document versions.
- Idempotent plain-text ingestion and asynchronous indexing.
- Tenant-authorised mixed lexical and semantic search with signed pagination.
- One-issuer OIDC identity and database-backed advisor membership.
- Durable authorisation decisions, append-only audit events, and type-specific provenance.
- Provider-neutral embeddings with local TEI by default and deterministic fake vectors in
  tests.

The design keeps these invariants:

- `nevis-global` is a bootstrap tenant, never an authorisation bypass.
- Every retrieval filters by the authorised tenant before ranking.
- Client PII never goes to an embedding provider.
- Document results retain tenant, source, document version, embedding profile, indexing
  decision, and search decision.
- Provider or model changes create a new profile and controlled re-index; vectors are not
  overwritten.
- Logs, metrics, traces, and audit metadata exclude customer text and credentials.
- Langfuse and OpenTelemetry are optional observability tools, not correctness dependencies.

See [architecture.md](architecture.md) for the implemented data flow and ranking design.

## Roadmap

### Completed

- Platform scaffold, migrations, health checks, CI gates, and `nevis-global` bootstrap.
- Tenant/advisor membership, OIDC identity, authorisation decisions, and audit events.
- Immutable document ingestion, durable indexing jobs, deterministic chunking, local TEI,
  fake embeddings, retry safety, and lineage.
- Tenant-authorised hybrid document search with fusion, thresholding, pagination, degradation,
  relevance fixtures, and performance harnesses.
- Tenant-owned clients, stable document association, and mixed client/document ranking.

The completed increment has 73 automated tests, strict OpenSpec validation, migration
upgrade/downgrade/drift checks, real-TEI Recall@5 and MRR of 1.0, and representative
100,000-document p95 of 683.40 ms.

### Next: operations and recovery

- Export bounded, low-cardinality metrics.
- Handle API and worker shutdown safely.
- Validate deployment configuration before serving traffic.
- Provide and rehearse PostgreSQL backup/restore and indexing replay.
- Record an operational-readiness checklist and its evidence.

Keep this milestone inside the modular monolith. Do not add Kubernetes, a broker, hosted
observability, or multi-region infrastructure.

### Later, when required

- Controlled re-indexing by tenant, document, or embedding profile.
- Hosted embedding-provider adapters for a named deployment.
- Source connectors, file validation, extraction/OCR, retention, and deletion workflows.
- Additional identity providers or administration features.
- Fuzzy or semantic client matching and ranking changes backed by labelled usage data.
- PostgreSQL partitioning, denormalisation, or ANN retrieval if representative measurements
  miss the target.

High availability, multi-region failover, a service mesh, a dedicated broker, a separate
vector database, and a custom policy engine are not current requirements.

## OpenSpec workflow

Use OpenSpec for a bounded feature with observable behaviour:

1. Propose the change against this plan and the canonical specs.
2. Review the proposal, delta specs, design, and tasks.
3. Apply and verify the implementation.
4. Sync delta specs into `openspec/specs/`.
5. Archive the completed change.

Do not create an OpenSpec change merely to restate this plan.
