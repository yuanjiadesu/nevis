# Deploy the UAT environment

The user acceptance testing (UAT) environment at `nevis.syntax.fitness` holds 50 fictional clients and their documents, and every visitor uses `local-advisor`. It is not production-ready: never add real client data. See [Roadmap](roadmap.md#work-starts-when) for the missing controls.

## Configure private access

Cloudflare Access is the UAT boundary:

1. Create a Cloudflare Tunnel from `nevis.syntax.fitness` to `http://api:8000`
2. Protect the hostname with Cloudflare Access
3. Allow named UAT users through one-time pins or an existing identity provider
4. Store the tunnel token on `mangabox`

Keep the API on its loopback host port. `cloudflared` is the only public ingress.

## Start UAT

Copy the working tree to `mangabox` without `.env`, `.git`, or build artifacts. Create `.env` from `.env.example` and set `CLOUDFLARE_TUNNEL_TOKEN`.

```bash
docker compose -f compose.yaml -f compose.preview.yaml \
  --profile tunnel up --build -d
docker compose exec -T api python scripts/provision_advisor.py local-advisor
docker compose exec -T \
  -e NEVIS_SEED_URL=http://127.0.0.1:8000 \
  api python scripts/seed_preview.py
curl http://127.0.0.1:8001/health/ready
```

Scripts inside the API container use port `8000`; host commands use `8001`. Wait for `reranker_provider: true` — search works before then but reports `hybrid_unreranked`.

## Enable fictional document summaries

Summaries are off by default. Review the [model provider boundary](model-providers.md#test-llm-summaries-locally), then set these `mangabox` secrets:

```dotenv
NEVIS_DOCUMENT_SUMMARIES_ENABLED=true
NEVIS_FICTIONAL_TEST_DATA=true
NEVIS_LLM_API_KEY=your_llm_api_key_here
```

Remaining provider values use `.env.example` defaults. Nevis sends complete document text, up to the 100,000-character input limit, directly to the configured LLM provider; it never sends partial text. Never enable this path for real client data. Missing or unsafe configuration stops startup, and provider failures do not affect indexing or document access.

After restarting the API and worker, check parity, reconcile current fictional versions, and verify the full path:

```bash
docker compose exec api nevis-summary-maintenance diagnose
docker compose exec api nevis-summary-maintenance reconcile --dry-run
docker compose exec api nevis-summary-maintenance reconcile
docker compose exec -T api python scripts/verify_preview_pipeline.py \
  --base-url http://127.0.0.1:8000
```

Use `--retry-failed` only after fixing the reported provider problem. Reconciliation is idempotent and skips historical versions.

## Update UAT

`mangabox` stores a file copy, not a Git checkout. Compare the deployed migration revision before replacing files:

```bash
docker exec nevis-postgres-1 \
  psql -U nevis -d nevis -t \
  -c 'SELECT version_num FROM alembic_version'
ls migrations/versions/
```

Sync with deletion enabled so removed migrations also leave the host. If the deployed revision is absent from the current chain, reset and reseed the fictional database instead of repairing its history.

## Check host capacity

The Intel N100 host has 4 cores and 16 GB RAM. The 50-client, 150-document stack used about 2.8 GB after startup, so allocate at least 4 GB. Reranking is CPU-bound and missed the 800 ms p95 target at five concurrent searches; [Scale constraints](scale-constraints.md) records the measurements and rules for comparison.

Run the evidence gate against the deployment:

```bash
docker compose exec -T -e NEVIS_EVALUATION_URL=http://127.0.0.1:8000 api \
  python scripts/evaluate_mixed_search.py
```

## Confirm readiness

Invite UAT users only when:

- The deployment contains fictional data only
- Cloudflare Access admits only named users
- The API is reachable only through the tunnel and loopback port
- `/health/ready` reports every dependency, including `reranker_provider`
- Search reports `hybrid`
- An invited user can open a client and search
- Logs contain no client or document text

## Stop UAT

```bash
docker compose -f compose.yaml -f compose.preview.yaml --profile tunnel down
```

This preserves data. Delete the named `postgres-data` and `tei-data` volumes only for fictional data — deletion is permanent.
