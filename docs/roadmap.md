# Know what comes next

Nevis gives an adviser one workspace for clients and their documents. The architecture targets 10,000 clients, 10–100 documents per client, and 10 KB of plain text per document on average.

## Current boundary

The original brief is complete: client search, semantic document search, optional summaries, tests, Docker Compose, OpenAPI documentation, and a deployed fictional-data environment. The implementation also adds tenant isolation, immutable revisions, lineage, idempotency, degraded search, and an adviser console.

The product is not ready for real client data. Recovery, retention, production browser identity, and operational evidence remain deliberate gates rather than hidden assumptions.

## Design rules

Use these rules for new work:

- Prefer the smallest design that meets the measured workload
- Keep identity and tenant authorisation outside ranking logic
- Keep client data out of model providers, logs, and metrics
- Change relevance only with labelled evaluation evidence
- Add infrastructure only for a measured limit or deployment need

See [Architecture](architecture.md) for boundaries and [Operations runbook](runbook.md) for operating limits.

## Work starts when

Do not add a change until one of these is already true:

- **Real client data**: production browser authentication, retention and deletion, tested backup and restore, replay tooling, and operational metrics
- **Named document source**: one connector with file validation and extraction; optical character recognition only for scanned inputs
- **Model change**: controlled re-indexing for affected documents without overwriting existing vectors
- **Labelled search failure**: ranking or matching changes against the repeatable evaluation set
- **Capacity failure**: PostgreSQL tuning first; partitioning, denormalisation, or approximate vector search only after measurement

The roadmap excludes speculative identity providers, tenant administration, Kubernetes, message brokers, separate vector databases, service meshes, multi-region failover, and custom policy engines.
