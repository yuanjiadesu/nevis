## 1. Report contract

- [x] 1.1 Add a shared report helper: timestamp, workload, ranking version, corpus counts, concurrency, warm-up, host/runtime, p50, p95, good-event ratio, SLO, pass/fail.
- [x] 1.2 Reject reports that include raw queries, document text, emails, vectors, tokens, or connection strings.

## 2. Existing harnesses

- [x] 2.1 Emit `search_eval` from `evaluate_mixed_search.py`. Keep quality assertions. Do not treat its p95 as the one-query gate.
- [x] 2.2 Emit `search_warm_p95` from `benchmark_search.py` and keep the 800 ms sequential gate.
- [x] 2.3 Emit `repo_capacity` from `benchmark_repository_search.py`. Default to 1,000 clients / 10,000 documents. Keep 10k/100k behind flags.

## 3. Docs

- [x] 3.1 Write `docs/performance.md` as a how-to: three workloads, 800 ms gate, commands, comparability rule. No host stats table.
- [x] 3.2 Link it from the runbook, search-engine, and scale-constraints.

## 4. Verification

- [x] 4.1 Add unit coverage for report shape, forbidden fields, workload names, and the 800 ms warm-search gate.
- [x] 4.2 Validate the OpenSpec change strictly.
