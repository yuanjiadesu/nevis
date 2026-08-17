## 1. Fix title search

- [x] 1.1 Add title and content evidence flags to search candidates and SQL results.
- [x] 1.2 Keep exact and prefix title matches after content reranking; keep existing gates for content and semantic matches.
- [x] 1.3 Deduplicate evidence per document, select the best preview, and bump the ranking version.
- [x] 1.4 Test exact titles, prefixes, unrelated bodies, rejected content, degraded modes, tenant isolation, and stable order.

## 2. Show summary state

- [x] 2.1 Add `not_requested`, `pending`, `processing`, `ready`, and `failed` to domain and API models.
- [x] 2.2 Return text only for `ready` without changing authorization, order, or pagination.
- [x] 2.3 Regenerate the API client and show concise states in the console.
- [x] 2.4 Test every state, mixed timelines, escaping, tenant isolation, and pagination.

## 3. Reconcile summary work

- [x] 3.1 Find current versions with missing or failed summary work.
- [x] 3.2 Add a dry-run operator command that creates missing work and retries failures only with an explicit flag.
- [x] 3.3 Keep retries bounded, audited, idempotent, and restricted to enabled fictional deployments.
- [x] 3.4 Test repeat and concurrent runs, historical exclusion, retries, config refusal, and output redaction.

## 4. Detect worker drift

- [x] 4.1 Add storage for a non-secret summary-worker heartbeat.
- [x] 4.2 Publish the heartbeat from the worker.
- [x] 4.3 Require a fresh matching heartbeat when summaries are enabled.
- [x] 4.4 Add safe aggregate diagnostics for states, failures, and heartbeat age.
- [x] 4.5 Test matching, missing, stale, disabled, and mismatched states.

## 5. Verify deployment

- [x] 5.1 Add a bounded UAT check for ingestion, indexing, exact-title search, and summary readiness.
- [x] 5.2 Update deployment and recovery docs.
- [x] 5.3 Run formatting, linting, typing, migrations, tests, search evaluation, strict OpenSpec validation, and the UAT check.
