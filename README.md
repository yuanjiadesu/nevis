# Nevis Search Platform

Nevis lets an authorised advisor search client records and their documents in one result
list. It keeps tenant access, source data, document versions, embedding profiles, and
authorisation decisions attributable. It returns search results, not generated answers.

The initial product increment is implemented. The next milestone is operations and recovery;
see the [platform plan](docs/platform-plan.md).

## Run locally

You need Docker Compose v2. For host development, install
[uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
cp .env.example .env
uv sync --all-groups
docker compose up --build
```

The first start downloads the pinned BGE-small model. The full stack needs about 2 GB of
Docker memory. TEI runs under emulation on Apple Silicon, so its first start can be slow.

Provision a local advisor:

```bash
docker compose exec api python scripts/provision_advisor.py local-advisor
```

Then visit `http://localhost:8001/docs` for the generated API documentation.

Check service health:

```bash
curl http://localhost:8001/health/live
curl http://localhost:8001/health/ready
```

Set `NEVIS_API_PORT=18000` before `docker compose up` if port 8001 is unavailable.

## API

All protected requests select a tenant. Local development identifies the advisor with
`X-Nevis-Advisor`; OIDC deployments use a bearer token and ignore that header.

| Endpoint | Purpose |
| --- | --- |
| `POST /v1/clients` | Create an idempotent tenant-owned client. |
| `GET /v1/clients/{id}` | Read a client and its provenance. |
| `POST /v1/clients/{id}/documents` | Accept a trusted plain-text document and queue indexing. |
| `GET /v1/documents/{id}` | Read current document and indexing state without content. |
| `GET /v1/document-versions/{id}` | Read version-specific indexing status. |
| `GET /search` | Search clients and documents with signed cursor pagination. |

Use a separate `Idempotency-Key` for each client creation and document ingestion command.
Unknown and cross-tenant resources return the same `404` response.

Local request context:

```text
X-Nevis-Tenant: nevis-global
X-Nevis-Advisor: local-advisor
```

OIDC request context:

```text
Authorization: Bearer <OIDC access token>
X-Nevis-Tenant: <tenant slug>
```

The database maps the verified OIDC `sub` to an advisor and checks active tenant membership.
Token tenant and role claims cannot grant access. Missing or invalid identity returns `401`,
missing membership returns `403`, conflicts return `409`, and unavailable required
dependencies return `503` without partial data.

## Search behaviour

`mixed-rrf-v1` places exact client email matches first, then exact full-name matches. It
combines general client text, document text, and document semantic matches by branch rank.
Client data stays in PostgreSQL and is never sent to the embedding provider.

Every result includes type-specific provenance. If TEI cannot embed a query, search keeps
the lexical client and document branches and reports `mode: lexical_degraded`.

## Quality checks

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pip-audit --local --skip-editable --progress-spinner off
uv run pytest
openspec validate --all --strict
```

The Compose verification, relevance, migration, and performance commands are in the
[operations runbook](docs/runbook.md).

## Documentation

- [Architecture](docs/architecture.md) explains trust boundaries, data flow, ranking, and
  measured limits.
- [Operations runbook](docs/runbook.md) covers deployment checks, failures, migrations, and
  recovery.
- [Platform plan](docs/platform-plan.md) records the quality bar and remaining roadmap.
- `/docs` and `/openapi.json` are the authoritative HTTP contracts.
- `openspec/specs/` contains canonical behavioural requirements; `openspec/changes/archive/`
  records why completed features changed.

## Deliberate limits

The platform accepts trusted plain text only. It does not yet provide file extraction, OCR,
source connectors, retention workflows, client mutation or deletion, generative answers,
fuzzy client matching, federation, or cross-tenant administration. We add those features
only through reviewed OpenSpec changes backed by a product or operational need.
