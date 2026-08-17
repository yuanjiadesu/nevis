## Context

See proposal.md for why. Three scripts already exist. CI already runs eval and the 800 ms warm search after seed. A 100k repository insert was killed (exit 137) on a 7.75 GiB Docker VM.

## Goals / Non-Goals

**Goals:**

- One report shape on the three existing scripts
- Keep the 800 ms one-pass gate
- Safe repository default
- A how-to page, not a stats ledger

**Non-Goals:**

- New runner or CLI
- Concurrency or seed-timing workloads
- CI / Compose smoke command changes
- k6, APM, error budgets, ranking changes

## Decisions

### Reuse the three scripts

Add a small shared report helper and have each script print that object. Rejected a runner: CI already calls the scripts, and a wrapper is extra surface.

### Publish p50 and p95; add a good-event ratio

`good_events / total_events` is requests under the workload threshold. The published gate stays p95 < 800 ms on `search_warm_p95`.

### Default repository size is 1,000 / 10,000

That size finished locally. 10k / 100k stays behind env flags.

### Docs are a how-to

`docs/performance.md` lists the three commands, the gate, and the comparability rule. Link from runbook, search-engine, and scale-constraints. No host tables.

## Risks / Trade-offs

- **Three commands instead of one** → Acceptable. The how-to names all three.
- **People still paste numbers** → The how-to says a report without context is unused.
- **100k remains unmeasured** → A scale-constraints fact, not this change.

## Migration Plan

1. Add the report helper.
2. Emit it from the three scripts.
3. Lower the repository default.
4. Write the how-to and retarget the three existing guides.

Rollback is the previous script output. No data migration.
