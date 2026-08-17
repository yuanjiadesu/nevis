# Measure performance

Run the existing harnesses. Each prints one JSON report. Compare two reports only when workload, ranking version, corpus, warm-up, and concurrency match.

## Workloads

| Workload | Command | Gate |
| --- | --- | --- |
| `search_eval` | `make eval` | Quality only. Its p95 is not the API gate. |
| `search_warm_p95` | `make bench` | Sequential warmed p95 must be ≤ 800 ms |
| `repo_capacity` | `make capacity` | Combined repository p95 ≤ 800 ms |

`search_eval` includes spelling retries. `search_warm_p95` is one query after a warm-up request.

## Run

Compose must be up. Then:

```bash
make measure
```

That seeds, then runs `eval`, `bench`, and `capacity`. `repo_capacity` defaults to 1,000 clients and 10,000 documents, then rolls back. For the unproven design shape: `make capacity-full`.

## Read a report

A valid report has `workload`, `runtime`, `warm_up`, `concurrency`, `p50_ms`, `p95_ms`, `good_event_ratio`, `slo_ms`, and `outcome`. It never includes queries, document text, emails, vectors, or connection strings.

A report without that context is unused. The 10,000-client design is still unproven.

See [Scale constraints](scale-constraints.md) for the design target and [Search engine](search-engine.md#measure-search-changes) for ranking changes.
