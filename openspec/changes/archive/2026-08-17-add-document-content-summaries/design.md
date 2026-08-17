## Context

Document versions are immutable. Indexing already runs through a leased worker. This change adds optional summaries for fictional test data in the `mangabox` UAT environment without making OpenCode a product dependency.

## Goals / Non-Goals

**Goals:**

- Tie each summary to one document version
- Keep indexing and document access available when generation fails
- Show generated text as secondary, untrusted content

**Non-Goals:**

- Search summaries or generated answers
- Multiple providers or local model hosting
- Automatic regeneration after model or prompt changes
- Use of summaries for retrieval, ranking, authorization, or audit content

## Decisions

### Call OpenCode directly

The worker injects provider identity, model, and endpoint into the OpenCode Chat Completions adapter from deployment settings. The defaults select OpenCode Go `mimo-v2.5`. The endpoint must use HTTPS, target `opencode.ai`, contain no credentials, query, or fragment, and end in `/chat/completions`; this keeps configuration from redirecting document content to another host. `OPENCODE_API_KEY` remains the only provider secret.

Configuration enables generation only for fictional test data. Startup fails when generation is enabled without the key or the test-data setting.

Use one narrow summarizer interface and one deterministic test fake. The fake is test-only, not a runtime fallback. Keep request construction, output parsing, bounds, and safe failures inside the adapter; do not add a local proxy or provider framework.

### Store work and output together

Create one `document_summaries` row per document version. Store:

- State: `pending`, `processing`, `ready`, or `failed`
- Bounded summary text
- Provider, model, and prompt version
- Attempts, lease data, safe failure code, and timestamps

Resolve tenant, client, source, and document lineage through the version. Do not duplicate it.

### Run summaries after indexing

Ingestion creates the summary row in the same transaction as the version. The worker drains indexing work before claiming summary work.

Use leases and bounded retries. Generation failures do not change indexing status, fail ingestion, or remove documents from search.

### Summarize complete documents only

Submit complete normalized content within the configured input bound. Leave the summary absent for empty or oversized content.

Request at most two sentences based only on document facts. Normalize and bound the response before storage. Treat the result as sensitive, untrusted display text.

Keep the provider token budget configurable and separate from the stored character bound. Reasoning models may consume provider output tokens before returning visible summary text.

### Keep the API nullable

Return `summary: string | null` from the authorized document resource and client timeline. Show present summaries beneath the title with an `AI-generated summary` label.

Do not return lifecycle details to the console. Do not add summaries to search results or search audit records.

## Risks / Trade-offs

- **Inaccurate output**: Label the summary, keep it short, and link to the source document
- **Real data reaches the test provider**: Require the fictional-test-data setting
- **Credential exposure**: Keep the key in `mangabox` secrets and out of storage, responses, logs, and audit records
- **Prompt injection**: Escape output and keep it outside search, authorization, and automated decisions
- **Mixed model output**: Record provider, model, and prompt version on every row
- **Worker contention**: Process indexing first and bound summary retries

## Migration Plan

Deploy with generation disabled. Add `OPENCODE_API_KEY` to the `mangabox` worker, verify the API with fictional content, then enable generation.

Do not backfill existing versions. Reseed fictional UAT data through normal ingestion when those documents need summaries.

Disable generation to roll back. Existing summaries remain attributable and can be omitted from API responses.
