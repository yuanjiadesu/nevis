# Nevis

Nevis gives an authorised adviser one place to find a client and the document passage that answers a query. Every result points back to stored source text. Nevis does not generate answers.

**Status:** local development and fictional-data user acceptance testing (UAT) only. Do not load real client data. Production still needs retention and deletion policy, tested backup and restore, indexing recovery tooling, production browser authentication, and operational metrics. See [Roadmap](docs/roadmap.md#work-starts-when).

## Start locally

Install Docker Compose v2. Host development also requires [uv](https://docs.astral.sh/uv), Python 3.12, and Node 22 with Corepack.

```bash
cp .env.example .env
uv sync --all-groups
docker compose up --build
docker compose exec api python scripts/provision_advisor.py local-advisor
```

The first start downloads the pinned embedding and reranking models. Allocate at least 4 GB to Docker; the UAT stack measured about 2.8 GB on an Intel N100, and Text Embeddings Inference (TEI) needs more headroom under Apple Silicon emulation. Both search models run locally, so no large language model (LLM) key is required — [Model providers](docs/model-providers.md) covers optional summaries.

Open the console at `http://localhost:8001/`, OpenAPI documentation at `/docs`, and readiness at `/health/ready`. Set `NEVIS_API_PORT=18000` before startup if `8001` is taken, then follow the [main workflow](docs/quickstart.md).

For frontend work, run `corepack enable`, `pnpm install --frozen-lockfile`, and `pnpm dev` from `web/`. Vite serves `http://localhost:5173` and proxies API calls to FastAPI.

## Follow one record

Each request begins with an adviser and one tenant. A client stays inside that boundary. A document belongs to the client, each edit creates an immutable version, and the worker indexes that version. Search returns the client or the strongest source passage with its lineage intact.

Three rules shape the system:

- Unknown and cross-tenant resources return the same `404`
- Client and document writes use an `Idempotency-Key`, so a safe retry cannot duplicate data
- Client fields stay in PostgreSQL; only document text and queries reach the local search models

Read [Architecture](docs/architecture.md) for the trust boundaries, [Documents](docs/documents.md) for the version lifecycle, and [Search engine](docs/search-engine.md) for ranking and degraded modes. The generated [OpenAPI contract](openapi.json) lists every endpoint.

## Try the search promises

Seed the fictional corpus with `docker compose exec -T api python scripts/seed_preview.py`, then try the cases from the original brief:

| Query | Expected result |
| --- | --- |
| `NevisWealth` | Client `John Doe` from name, email, or description search |
| `neviswealth.com` | Clients with that complete email domain |
| `address proof` | `Household electricity statement`, whose text says `utility bill` |

An abridged document result shows the passage that earned the match:

```json
{
  "ranking_version": "mixed-rrf-v5",
  "mode": "hybrid",
  "results": [
    {
      "type": "document",
      "title": "Household electricity statement",
      "snippet": "The document is a utility bill from an electricity supplier. It shows the account holder's name and current residential address."
    }
  ],
  "next_cursor": null
}
```

The real response adds scores, branch ranks, and tenant, document, version, model, indexing, and search provenance.

## Run checks

Start the integration database through the [operations runbook](docs/runbook.md) before combined coverage.

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pip-audit --local --skip-editable --progress-spinner off
NEVIS_TEST_DATABASE_URL=postgresql+asyncpg://nevis:nevis@localhost:5434/nevis ./scripts/coverage.sh
uv run playwright install chromium
uv run pytest tests/browser
cd web && pnpm lint && pnpm test:coverage && pnpm build && cd ..
uv run python scripts/export_openapi.py
cd web && pnpm generate:api && cd ..
git diff --exit-code -- openapi.json web/src/api.generated.ts
pnpm dlx @fission-ai/openspec@1.9.0 validate --all --strict
```

The remaining guides cover the [console](docs/console.md), [UAT deployment](docs/deployment.md), [roadmap](docs/roadmap.md), and [scale constraints](docs/scale-constraints.md).

## Know the limits

Nevis accepts trusted plain text only. It has no file extraction, optical character recognition, source connectors, deletion workflow, generated answers, federation, cross-tenant administration, or requeue command for failed indexing.

The design targets 10,000 clients but has not passed a representative capacity test. [Scale constraints](docs/scale-constraints.md) gives the evidence, bottlenecks, and trigger for changing the architecture.
