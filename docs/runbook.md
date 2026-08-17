# Operate Nevis

Use this runbook for local and user acceptance testing (UAT) operations. Never copy tokens, client data, document content, raw queries, vectors, or connection strings into logs or tickets.

## Start and inspect services

```bash
docker compose up --build
docker compose ps
curl http://localhost:8001/health/live
curl http://localhost:8001/health/ready
docker compose down
```

`/health/live` checks the API process. `/health/ready` checks PostgreSQL, Text Embeddings Inference (TEI), OpenID Connect (OIDC) keys when enabled, the evidence ranker, and summary-worker parity when enabled.

After a readiness failure, start here:

| Dependency | First check |
| --- | --- |
| `database` | Run `docker compose logs postgres migrate` and confirm migrations |
| `embedding_provider` | Run `docker compose logs tei` and allow the first model download |
| `reranker_provider` | Run `docker compose logs reranker`; search can use `hybrid_unreranked` |
| `identity_provider` | Check issuer, audience, JSON Web Key Set reachability, TLS, and DNS |
| `summary_worker` | Run `nevis-summary-maintenance diagnose`; restart the API and worker if capability hashes differ |

## Manage identity and membership

```bash
docker compose exec api python scripts/provision_advisor.py advisor_external_id
```

UAT uses fictional data and `local-advisor` in `nevis-global` behind Cloudflare Access. It is not a production identity boundary.

Production API integrations map the verified OIDC `sub` to `advisors.external_id` and require active membership in `X-Nevis-Tenant`. Nevis does not serve the browser console with production authentication.

Publish a new signing key before issuing tokens with its `kid`, and keep the old key through the token lifetime and key-cache window. An unknown `kid` triggers one rate-limited refresh, and verification fails closed after the maximum stale-key window.

Identity failures return `401`, missing membership `403`, cross-tenant resources `404`, and an unavailable required identity dependency `503` without data.

## Apply migrations

Compose runs migrations through the `migrate` service. To inspect or apply them from the host, set `NEVIS_DATABASE_URL` and run:

```bash
uv run alembic current
uv run alembic upgrade head
uv run alembic check
```

Use `uv run alembic downgrade -1` only with disposable local data. For live data, restore the previous application image and follow a reviewed migration plan; roll back the application before the schema.

Migration `20260817_0010` removes documents without a client because Nevis cannot infer ownership. Review that deletion before applying it to older data.

## Diagnose indexing failures

Inspect document or version status first. Failed jobs expose safe codes, not content or provider details.

- `embedding_runtime_unavailable`: inspect `docker compose logs tei worker` and restore TEI. Failed indexing is terminal and this release has no supported requeue command
- Interrupted `processing`: wait for the lease to expire so another worker can reclaim it

## Recover missing summaries

Confirm the API and worker use the same [model provider configuration](model-providers.md#test-llm-summaries-locally), then:

1. Run `nevis-summary-maintenance diagnose`.
2. Recreate API and worker if their capability hashes differ.
3. Run `nevis-summary-maintenance reconcile --dry-run`, then `reconcile`.
4. Use `--retry-failed` only after fixing the safe failure code.
5. Run `scripts/verify_preview_pipeline.py`.

Do not reset the database for routine summary recovery.

Preserve failed indexing lineage:

- Failed version: do not create a replacement version or delete chunks to force a retry
- Disposable local or fictional UAT data: reset the data volumes and reseed after fixing the cause
- Non-disposable data: retain the failed job unchanged until reviewed recovery tooling exists; do not edit job rows directly

Add and rehearse backup, restore, and indexing replay before accepting real client data.

## Diagnose search failures

`lexical_degraded` means query embedding failed; restore TEI without changing the active profile. `hybrid_unreranked` means authorised candidates returned without final evidence ranking. `503 search unavailable` means a required database, profile, or audit operation failed.

The semantic candidate floor is `0.60` and the evidence ranker floor is `0.005`. Change either value, branch weights, ordering, or model only with a new ranking version and labelled evidence.

Run provider-backed checks:

```bash
docker compose exec -T -e NEVIS_EVALUATION_URL=http://127.0.0.1:8000 api \
  python scripts/evaluate_mixed_search.py
docker compose exec api python scripts/benchmark_search.py
```

Run the repository capacity harness from the host:

```bash
NEVIS_DATABASE_URL=postgresql+asyncpg://nevis:nevis@localhost:5432/nevis \
  uv run python scripts/benchmark_repository_search.py
```

Before admitting a tenant above 10,000 indexed documents, repeat with `NEVIS_BENCHMARK_DOCUMENTS=100000`. Inspect tenant-scoped plans with synthetic queries:

```bash
docker compose exec -T postgres psql -U nevis -d nevis \
  -f /dev/stdin < scripts/explain_search.sql
```

See [Search engine](search-engine.md#measure-search-changes) for current measurements.

## Run database-backed tests

```bash
docker compose -f compose.yaml -f compose.test.yaml -p nevis-integration \
  up --build --wait postgres migrate
uv run pytest tests/integration
docker compose -f compose.yaml -f compose.test.yaml -p nevis-integration down -v
```

The default test database is `postgresql+asyncpg://nevis:nevis@localhost:5434/nevis`; set `NEVIS_TEST_DATABASE_URL` to use another. An unreachable configured database fails the suite.

Use `docker compose down -v` only for disposable local data — it deletes database and model volumes, while plain `docker compose down` preserves them.
