## 1. Backend Coverage

- [x] 1.1 Add and lock `pytest-cov`, then configure branch measurement, source selection, missing-line output, and an 85% total threshold.
- [x] 1.2 Add reproducible commands that erase, collect, append, and report combined non-integration and PostgreSQL integration coverage.
- [x] 1.3 Add focused tests for uncovered client orchestration, provider failure boundaries, and worker edge paths needed to keep the combined suite above the threshold without exclusions.

## 2. Frontend Behavior Coverage

- [x] 2.1 Add and lock the Vitest V8 coverage provider, jsdom, and Testing Library dependencies with shared test setup.
- [x] 2.2 Test the API client's success and failure handling, request encoding, mutation bodies, and pagination parameters.
- [x] 2.3 Test client management behavior for loading, empty, error, validation, creation/update success, and pagination states.
- [x] 2.4 Test document management behavior for loading, empty, error, revision, timeline, pagination, and every safe summary state.
- [x] 2.5 Test global search behavior for query routing, loading, empty, degraded/error, mixed results, pagination, and safe highlighting/rendering.
- [x] 2.6 Configure frontend coverage exclusions and enforce 60% statements, lines, and functions with 50% branch coverage.

## 3. Warning Cleanup

- [x] 3.1 Adopt the supported FastAPI/Starlette test-client dependency path and verify workspace tests no longer emit the httpx deprecation warning.
- [x] 3.2 Replace deprecated per-request test cookies with client-level cookie state and verify integration tests remain isolated.

## 4. CI Consistency Gates

- [x] 4.1 Update CI to combine backend coverage across both pytest stages and fail below 85%.
- [x] 4.2 Update CI to run frontend tests with coverage and enforce the configured thresholds.
- [x] 4.3 Regenerate OpenAPI and TypeScript contracts in CI and fail on a diff in either checked-in output.
- [x] 4.4 Run strict validation with pinned `@fission-ai/openspec@1.9.0` in CI.
- [x] 4.5 Document the matching local commands and record the search-orchestration complexity refactor as separate follow-up work.

## 5. Verification

- [x] 5.1 Run Python formatting, linting, strict typing, dependency audit, combined coverage, migration, and integration checks.
- [x] 5.2 Run frontend lint, coverage, and production build checks under the declared Node 22 runtime.
- [x] 5.3 Regenerate both API contracts, confirm a clean targeted diff, and run strict OpenSpec validation.
