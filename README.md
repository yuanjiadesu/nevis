# Nevis

An authorised adviser finds a client, or the stored passage that answers a query. Every result points at source text. Nevis does not generate answers. [Design choices](docs/architecture.md#design-choices) records the main trade-offs.

Local and fictional-data UAT only. Do not load real client data. See [Roadmap](docs/roadmap.md#work-starts-when) for what production still needs.

## Run

Needs Docker Compose v2. Host checks also need [uv](https://docs.astral.sh/uv), Python 3.12, and Node 22.

```bash
make setup
make up
make provision
make seed
```

The first start downloads the pinned search models. Give Docker at least 4 GB. No LLM key is required; [model providers](docs/model-providers.md) cover optional summaries.

Console: `http://localhost:8001/`. OpenAPI: `/docs`. Ready: `/health/ready`. If `8001` is taken, set `NEVIS_API_PORT=18000` before `make up`. `make` lists the other commands; `make web` is the Vite console.

## Try the hosted console

A fictional-data UAT instance is at [nevis.syntax.fitness](https://nevis.syntax.fitness). Cloudflare Access is in front of it; ask for an invite (email one-time PIN). Every visitor is `local-advisor` in `nevis-global`. Do not add real client data.

1. Open the site and complete the Access prompt
2. Open a client, or stay on the workspace
3. Press `Cmd/Ctrl+K`, type a query, submit
4. Open a result to see the client, source passage, and document version

| Query | Result |
| --- | --- |
| `NevisWealth` | Client `John Doe` |
| `neviswealth.com` | Clients on that email domain |
| `address proof` | `Household electricity statement` (`utility bill` in the text) |

The same queries work on the local console after `make seed`. Create → ingest → search is in the [quickstart](docs/quickstart.md); the [console guide](docs/console.md) is the full UI path.

An abridged document hit looks like:

```json
{
  "ranking_version": "mixed-rrf-v5",
  "mode": "hybrid",
  "results": [
    {
      "type": "document",
      "title": "Household electricity statement",
      "snippet": "The document is a utility bill from an electricity supplier."
    }
  ]
}
```

The live response also has scores, tenant, version, and indexing provenance. API calls from outside the console need `X-Nevis-Tenant: nevis-global` and `X-Nevis-Advisor: local-advisor`.

## Limits

Trusted plain text only. No file extraction, OCR, connectors, deletion workflow, generated answers, federation, or indexing requeue.

The design targets 10,000 clients and has not passed a representative capacity test. [Scale constraints](docs/scale-constraints.md) states the evidence and when to change the architecture.

## Docs

[Architecture](docs/architecture.md) · [Clients](docs/clients.md) · [Documents](docs/documents.md) · [Search](docs/search-engine.md) · [Console](docs/console.md) · [Operate](docs/runbook.md) · [Measure](docs/performance.md) · [Reliability](docs/reliability.md) · [Deploy UAT](docs/deployment.md) · [OpenAPI](openapi.json) · [OpenSpec](openspec/specs/)

`make check` is the host quality gate. Combined coverage needs `make test-db-up && make coverage`.
