## 1. Store and generate summaries

- [x] 1.1 Add one version-keyed summary table with state, bounded output, provenance, attempts, lease data, safe failure, and timestamps.
- [x] 1.2 Add a narrow summarizer interface, bounded result type, and deterministic test fake.
- [x] 1.3 Inject validated OpenCode provider identity, model, Chat Completions endpoint, and provider token budget into the adapter, with OpenCode Go `mimo-v2.5` defaults, deterministic sampling, `store: false`, bounded input and stored output, timeouts, and bounded retries. Keep `OPENCODE_API_KEY` as the only provider secret and require the fictional-test-data setting.

## 2. Process summaries asynchronously

- [x] 2.1 Create pending summary work in the document-version transaction when generation is enabled.
- [x] 2.2 Extend the worker to process indexing first, then lease and complete summary work without duplicates.
- [x] 2.3 Leave summaries absent for disabled, empty, oversized, exhausted, or unsafe work. Keep sensitive values out of logs and audit records.

## 3. Return and display summaries

- [x] 3.1 Return the current version’s nullable summary from the authorized document resource and client timeline.
- [x] 3.2 Show present summaries beneath document titles with an `AI-generated summary` label. Keep search results unchanged.
- [x] 3.3 Regenerate the OpenAPI client. Document `mangabox` secret setup, disabled behavior, and reseeding through normal ingestion.

## 4. Verify behavior

- [x] 4.1 Test version scoping, transactional work, lease recovery, retries, indexing priority, missing or unsafe configuration, injected OpenCode request identity, and OpenCode failure.
- [x] 4.2 Test tenant isolation, input and output bounds, escaped output, safe telemetry, and exclusion from search.
- [x] 4.3 Review a representative seeded sample. Run formatting, linting, typing, focused tests, strict OpenSpec validation, and confirm persisted summaries do not cause subsequent provider calls.
