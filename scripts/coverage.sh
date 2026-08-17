#!/usr/bin/env bash

set -euo pipefail

if [[ -z "${NEVIS_TEST_DATABASE_URL:-}" ]]; then
  echo "NEVIS_TEST_DATABASE_URL must point to the PostgreSQL integration-test database." >&2
  exit 2
fi

uv run coverage erase
uv run pytest --cov=nevis --cov-report= --cov-fail-under=0 --ignore=tests/integration
uv run pytest --cov=nevis --cov-append --cov-report= --cov-fail-under=0 tests/integration
uv run coverage report
