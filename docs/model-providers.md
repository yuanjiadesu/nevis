# Configure model providers

Nevis runs search models locally by default. Only optional document summaries call a remote large language model (LLM), and that path accepts fictional data only.

## Know which provider handles each task

| Task | Default | Data sent |
| --- | --- | --- |
| Embedding | Local Text Embeddings Inference (TEI) | Document chunks and search queries |
| Evidence ranking | Local TEI | Search queries and authorised candidate passages |
| Document summary | Configured OpenAI-compatible provider (disabled) | Complete document text |

Client fields never reach a model provider. The default Compose stack starts both TEI services and needs no external credential.

## Respect summary limits

| Behavior | Default |
| --- | ---: |
| Input eligibility | Non-empty current version, at most 100,000 characters |
| Stored output | At most 500 characters and two sentences |
| Provider output allowance | 500 tokens |
| Provider timeout | 15 seconds |
| Attempts | 3 |
| Work lease | 60 seconds |
| Worker heartbeat | Every 5 seconds; stale after 20 seconds |

Nevis submits the complete document only when it fits the input limit; it never truncates or partially summarizes oversized content. The single worker always clears indexing work before summary work, so sustained ingestion can delay summaries indefinitely.

With summaries enabled, readiness checks for a fresh worker heartbeat with matching enabled state, provider, model, and prompt version. It does not call the remote LLM or compare endpoint, size, timeout, retry, lease, or credential settings, so a ready response confirms worker presence and partial configuration parity — not provider availability.

## Test search models locally

Start the stack with the checked-in model names and revisions:

```bash
cp .env.example .env
docker compose up --build
```

Wait until `embedding_provider` and `reranker_provider` are `true`, then provision the adviser, seed the fictional corpus, and run the provider-backed relevance check inside the API container:

```bash
curl --fail http://localhost:8001/health/ready
docker compose exec api python scripts/provision_advisor.py local-advisor
docker compose exec -T api python scripts/seed_preview.py
docker compose exec -T \
  -e NEVIS_EVALUATION_URL=http://127.0.0.1:8000 \
  api python scripts/evaluate_mixed_search.py
```

Do not change a model, revision, dimensions, thresholds, or ranking policy without a new ranking version and labelled evaluation evidence.

## Test LLM summaries locally

Use only fictional documents. Add these values to `.env`:

```dotenv
NEVIS_DOCUMENT_SUMMARIES_ENABLED=true
NEVIS_FICTIONAL_TEST_DATA=true
NEVIS_LLM_PROVIDER=opencode-go
NEVIS_LLM_MODEL=mimo-v2.5
NEVIS_LLM_ENDPOINT=https://opencode.ai/zen/go/v1/chat/completions
NEVIS_LLM_API_KEY=your_llm_api_key_here
```

Only the OpenCode Chat Completions host is trusted: the endpoint must use HTTPS, target `opencode.ai`, carry no credentials, query, or fragment, and end in `/chat/completions`. `.env.example` holds the supported configuration.

Recreate the API and worker so both receive the same configuration, reconcile versions created before summaries were enabled, then verify a new document from ingestion through summary delivery:

```bash
docker compose up --build -d api worker
docker compose exec api python scripts/provision_advisor.py local-advisor
docker compose exec -T api python scripts/seed_preview.py
docker compose exec api nevis-summary-maintenance reconcile --dry-run
docker compose exec api nevis-summary-maintenance reconcile
docker compose exec -T api python scripts/verify_preview_pipeline.py \
  --base-url http://127.0.0.1:8000
```

Never commit `.env` or an API key. Disable summaries before loading non-fictional data.

## Run tests without provider credentials

Unit and integration tests need no LLM key: summary adapter tests mock the remote response, and search unit tests use deterministic providers.

```bash
uv run pytest tests/unit/test_provider_boundaries.py \
  tests/unit/test_summarization.py
```

Use the Compose relevance check above when a change must exercise the real local embedding and reranking services.
