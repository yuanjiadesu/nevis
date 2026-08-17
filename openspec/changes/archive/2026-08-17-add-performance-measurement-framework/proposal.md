## Why

The three existing harnesses emit different JSON and omit host, corpus, and warm-up. People then paste incomparable numbers into docs.

## What Changes

- Give the three existing scripts one report shape with workload name, context, p50/p95, and pass/fail.
- Keep `search_eval` quality checks separate from the 800 ms `search_warm_p95` gate.
- Default the repository harness to 1,000 clients / 10,000 documents. The 100k shape stays opt-in.
- Add a short how-to. Do not keep a handwritten stats ledger.

Out of scope: a new runner, concurrency workload, seed-timing workload, CI command changes, k6, APM.

## Capabilities

### New Capabilities

- `performance-measurement`: Named reports from the existing harnesses, with required context and an 800 ms one-pass gate.

### Modified Capabilities

None.

## Impact

Edits `scripts/evaluate_mixed_search.py`, `scripts/benchmark_search.py`, `scripts/benchmark_repository_search.py`, a small shared report helper, unit tests, `docs/performance.md`, and links from the runbook, search-engine, and scale-constraints. CI and Compose smoke keep calling the same two scripts. No API or ranking change.
