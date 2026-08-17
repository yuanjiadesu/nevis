## Context

The Python suite currently passes 88 non-integration tests and 31 PostgreSQL integration tests. A branch-aware diagnostic run measured 87% total coverage, but coverage tooling is not a development dependency and CI runs the two suites without combining or enforcing their data. The React console has five Vitest cases in two files and one broad Playwright-backed Python browser scenario; Vitest coverage is neither installed nor configured.

CI already performs formatting, linting, strict typing, dependency auditing, migration round trips, integration tests, Compose smoke tests, search evaluation, and a production build. It does not validate OpenSpec or regenerate and compare the checked-in OpenAPI and TypeScript contracts. The repository is under active development, so new gates must start from measured, achievable baselines and remain deterministic.

## Goals / Non-Goals

**Goals:**

- Make branch-aware backend and frontend coverage visible and regression-blocking in CI.
- Exercise critical console behavior at the component boundary, including success, empty, loading, error, pagination, form validation, and safe summary rendering states.
- Fail CI when OpenSpec artifacts or generated API contracts drift.
- Remove known test deprecation warnings so future warnings remain actionable.
- Keep all checks reproducible from documented local commands.

**Non-Goals:**

- Achieve 100% coverage or optimize for a coverage number over meaningful behavior.
- Refactor search ranking, OIDC, settings, or repository architecture in the same change.
- Change API or console behavior.
- Add visual-regression or cross-browser infrastructure.

## Decisions

### Combine backend coverage across the existing suites

Add `pytest-cov` as a locked development dependency and configure coverage for `src/nevis`, branch measurement, useful missing-line output, and an initial 85% total threshold. CI will run the non-integration suite without a final report, append the PostgreSQL integration suite to the same coverage data after the database is available, then emit one report and enforce the threshold.

This preserves the existing early, database-independent test stage while measuring the real combined suite. Enforcing each suite independently was rejected because integration-owned database and worker paths make the non-integration number misleadingly low. An 85% starting gate is below the measured 87% baseline, leaving a small stability margin while immediately preventing material regression.

### Establish frontend behavior coverage before enforcing a baseline

Add the Vitest V8 coverage provider plus Testing Library and jsdom for interaction-level component tests. Cover critical behaviors in the client, document, and global-search features rather than snapshotting large component trees. Start with thresholds of 60% for statements, lines, and functions and 50% for branches, then ratchet them upward as meaningful cases are added.

A baseline matching the current five tests would legitimize the known gap. A backend-equivalent threshold would encourage shallow assertions and make the first change too large. Frontend coverage excludes generated API types and entrypoint files.

### Verify generated contracts by regeneration and diff

CI will run the existing Python OpenAPI exporter, regenerate `web/src/api.generated.ts`, and use `git diff --exit-code` on both checked-in outputs. This tests the actual generation path and produces an actionable diff. Comparing timestamps or custom hashes was rejected because those approaches hide the content developers need to review.

### Validate OpenSpec with a pinned CLI

CI will invoke `@fission-ai/openspec` at the repository's current CLI version and run `validate --all --strict`. Pinning avoids runner-dependent behavior while keeping the validation independent of local global installation.

### Treat complexity reduction as a separate change

The audit identified `search_documents` as the largest complexity hotspot, but splitting it while adding coverage infrastructure would mix behavior-preserving architecture work with gate adoption. This change will record a follow-up recommendation after the new gates land; a separate OpenSpec change can define the extraction and use the enforced coverage as its safety net.

### Eliminate warnings at their source

Use the supported FastAPI/Starlette test-client dependency path and set persistent cookies on the client rather than passing deprecated per-request cookies. Do not blanket-filter deprecation warnings, because suppression would conceal future dependency breakage.

## Risks / Trade-offs

- **Coverage differs between local and CI execution** → Pin tooling, use the same commands in documentation and CI, and measure the combined suite consistently.
- **Parallel or separate pytest processes lose coverage data** → Explicitly erase at the start, append during the integration stage, and report only after both stages succeed.
- **Coverage targets reward trivial tests** → Prefer user-visible state and boundary assertions; treat thresholds as a floor, not the test strategy.
- **Frontend tests become tightly coupled to markup** → Query by accessible roles, labels, and observable behavior rather than class names or full snapshots.
- **Generated-contract checks rewrite files during CI** → Limit the final diff check to the two generated outputs and fail with their content diff.
- **Pinned OpenSpec CLI becomes stale** → Update the pin deliberately when the repository adopts a newer schema/tool version.

## Migration Plan

1. Add and lock backend and frontend coverage/test dependencies.
2. Add focused frontend cases and configure thresholds only after the suite clears them locally.
3. Configure combined backend coverage and confirm the current suite remains above 85%.
4. Fix warning sources and run tests with warning output clean.
5. Add OpenSpec and generated-contract checks to CI.
6. Update local check documentation and run the complete CI-equivalent suite.

Rollback removes the new thresholds and CI commands while retaining the added behavioral tests. No runtime deployment or data migration is required.
