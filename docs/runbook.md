# Operations runbook

Use this runbook for local and deployment checks. Never copy tokens, client data, document
content, raw queries, vectors, or connection strings into logs or tickets.

## Start, inspect, and stop

```bash
docker compose up --build
docker compose ps
curl http://localhost:8001/health/live
curl http://localhost:8001/health/ready
docker compose down
```

`/health/live` reports only whether the API process is running. `/health/ready` checks
PostgreSQL, TEI, and OIDC verification keys when OIDC is enabled.

| Readiness failure | First checks |
| --- | --- |
| `database` | `docker compose logs postgres migrate`; confirm migrations completed. |
| `embedding_provider` | `docker compose logs tei`; allow time for the first model download. |
| `identity_provider` | Check issuer, audience, JWKS reachability, TLS, and DNS without logging credentials. |

## Identity and membership

Provision local membership with:

```bash
docker compose exec api python scripts/provision_advisor.py <advisor-external-id>
```

In an OIDC deployment, use the verified `sub` as `advisors.external_id`. Terminate TLS at the
ingress, forward `Authorization` and `X-Nevis-Tenant`, and strip `X-Nevis-Advisor`. Configure
one HTTPS issuer and audience and use a non-placeholder cursor signing key.

Publish a new signing key in JWKS before issuing tokens with its `kid`. Keep the old key until
old tokens and cache windows expire. An unknown `kid` triggers one rate-limited refresh.
During an issuer outage, cached keys work only within the configured maximum-stale window;
after that, verification fails closed.

Identity failures return `401`, verified advisors without active membership return `403`,
cross-tenant resource reads return `404`, and an unavailable identity dependency returns
`503` without protected data.

## Migrations and rollback

Compose applies migrations through the `migrate` service. Inspect or apply them from the host
with `NEVIS_DATABASE_URL` set:

```bash
uv run alembic current
uv run alembic upgrade head
uv run alembic check
```

Downgrade only disposable local data with `uv run alembic downgrade -1`. With live data,
restore the previous application image and follow a reviewed migration plan. Roll back the
application before the schema. Never roll an OIDC deployment back to local-header mode.

The client migration intentionally leaves legacy documents with `client_id = NULL`. Do not
invent ownership during migration or recovery.

## Indexing failures

Inspect the document or version status endpoint first. A failed job exposes a safe error code,
not source content or provider details.

- For `embedding_runtime_unavailable`, inspect `docker compose logs tei worker`, restore TEI,
  then use the reviewed replay procedure.
- A worker may reclaim an interrupted `processing` job after its lease expires.
- Do not create a replacement document version or delete chunks to force a retry.
- Keep the original tenant, version, profile, and authorisation decision on every replay.

Backup/restore and indexing replay tooling are the next operational milestone. Add and
rehearse both before the first live-data deployment.

## Search and relevance

`mode: lexical_degraded` means PostgreSQL and authorisation succeeded but query embedding did
not. Restore TEI; do not change the active profile as an incident workaround. A `503 search
unavailable` means a required database, profile, or audit operation failed, so no partial
results were returned.

The default semantic threshold is `0.70`. Change the threshold, branch weights, precedence, or
cursor ordering only with a new ranking version and labelled evaluation evidence.

Run the real-provider checks against the Compose stack:

```bash
docker compose exec api python scripts/evaluate_mixed_search.py
docker compose exec api python scripts/benchmark_search.py
```

Run the rollback-only repository capacity harness from the host:

```bash
NEVIS_DATABASE_URL=postgresql+asyncpg://nevis:nevis@localhost:5432/nevis \
  uv run python scripts/benchmark_repository_search.py
```

Before admitting a tenant above 10,000 indexed documents, repeat it with
`NEVIS_BENCHMARK_DOCUMENTS=100000`. Inspect tenant-scoped plans with synthetic queries only:

```bash
docker compose exec -T postgres psql -U nevis -d nevis \
  -f /dev/stdin < scripts/explain_search.sql
```

The current measurements and capacity boundary are in
[architecture.md](architecture.md#measured-envelope).

## Verification

Run the local quality gates from the README, then exercise the database-backed suite:

```bash
docker compose -f compose.yaml -f compose.test.yaml -p nevis-integration \
  up --build --wait postgres migrate
NEVIS_TEST_DATABASE_URL=postgresql+asyncpg://nevis:nevis@localhost:5434/nevis \
  uv run pytest tests/integration
docker compose -f compose.yaml -f compose.test.yaml -p nevis-integration down -v
```

Use `docker compose down -v` only for disposable local data. It deletes the database and model
volumes. Normal `docker compose down` preserves both.
