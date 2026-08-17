## Why

Nevis has strong backend tests and static checks, but CI does not measure or enforce coverage, the React console has only a small test surface, and generated contracts and OpenSpec artifacts can drift without failing a pull request. These gaps allow regressions despite an otherwise healthy quality baseline.

## What Changes

- Measure branch-aware Python coverage across the non-integration and PostgreSQL integration suites and enforce a ratchetable minimum.
- Measure frontend coverage and add focused tests for critical client, document, and search behaviors before enforcing a realistic baseline.
- Make CI reject invalid OpenSpec artifacts and stale generated OpenAPI/TypeScript contracts.
- Resolve the currently observed test deprecation warnings.
- Record the high-complexity search orchestration as follow-up refactoring work rather than mixing a behavior-preserving redesign into the quality-gate change.

## Capabilities

### New Capabilities

None. This is a tooling and test-hardening change with no new externally observable product behavior.

### Modified Capabilities

None. Existing API, console, authorization, search, ingestion, and summarization requirements remain unchanged.

## Impact

This affects Python and frontend development dependencies, pytest and Vitest configuration, focused test files, generated-contract verification scripts, and the GitHub Actions quality workflow. Pull requests that reduce coverage below the adopted baselines, invalidate OpenSpec artifacts, or leave generated contracts stale will fail CI.
