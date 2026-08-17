## Context

Title and content matches currently share one candidate type. The reranker sees only body text, so it can reject an exact title match.

Summary work is created only when the API enables it. The worker enables it separately. The API returns `summary: null` for missing, pending, and failed work.

## Goals / Non-Goals

**Goals:**

- Keep title matches without weakening content filtering.
- Show and recover summary state.
- Detect API-worker config drift.
- Verify the full UAT flow.

**Non-Goals:**

- Search or authorize with summaries.
- Backfill historical versions by default.
- Change search storage or model providers.
- Enable summaries for real data.

## Decisions

### Keep evidence type

Add title, content, and semantic flags to search candidates.

The reranker still scores body passages. Final results include:

- documents with exact or prefix title evidence;
- documents whose content or semantic evidence passes reranking.

A title match may use a passing body passage as its preview. Otherwise it uses a bounded body opening.

Do not join title and body before reranking. That would hide the evidence source and change model thresholds.

Fuzzy titles keep their current lower match band. Exact and prefix titles stay in the general band.

### Add summary state

Return `summary_status` as one of:

- `not_requested`
- `pending`
- `processing`
- `ready`
- `failed`

Only `ready` returns summary text. `not_requested` means no summary row exists; it does not guess why.

The console shows ready text as AI-generated. Other states show short status text.

### Add explicit reconciliation

Add an idempotent operator command for enabled fictional deployments.

Default behavior:

- find eligible current versions without summary rows;
- create pending rows;
- report failed rows;
- ignore historical versions;
- never call the provider directly.

An explicit retry flag requeues eligible failed rows and records an audit event. Ready, pending, and processing rows are never duplicated.

Do not backfill on startup. A config change must not silently submit a large corpus.

### Add a worker heartbeat

Store a summary-worker heartbeat in PostgreSQL. It contains a non-secret hash of enabled state, provider, model, prompt, and pipeline version.

When summaries are enabled, API readiness requires a fresh matching heartbeat. When disabled, summaries do not gate readiness.

This works across hosts and proves a live worker loaded the expected config. It does not store credentials or endpoints.

### Keep diagnostics private

Add an operator command that reports:

- current-version summary state counts;
- safe failure-code counts;
- heartbeat age;
- expected and actual capability match.

It must not print client data, document data, summaries, prompts, provider responses, endpoints, or credentials.

### Add a UAT check

Create or revise a fictional document whose unique title is absent from its body. Poll until:

1. indexing completes;
2. exact-title search finds it;
3. summary state becomes `ready`.

Use stable idempotency keys and bounded timeouts. Check state, not generated wording.

## Risks / Trade-offs

- **Weak title-only preview** → Show a bounded body opening.
- **Too many summary jobs** → Reconcile current versions only and support dry-run.
- **Repeated provider cost** → Retry failed work only with an explicit flag.
- **Brief rollout failure** → Start the worker before readiness checks.
- **Diagnostic data leakage** → Keep diagnostics operator-only and aggregate.

## Migration Plan

1. Add heartbeat storage and `summary_status`.
2. Deploy worker heartbeat and API readiness together.
3. Add evidence flags and bump the ranking version.
4. Regenerate clients and update the console.
5. Align API and worker settings.
6. Dry-run, then apply reconciliation.
7. Run the UAT check.

Rollback restores the old ranking and API shape. Existing summary rows and heartbeats can remain. Disable summary generation before removing worker support.
