# Nevis operator commands. Run `make` for the list.
# Override with `make up COMPOSE="docker compose -p nevis"`.

COMPOSE   ?= docker compose
API       = $(COMPOSE) exec -T api
UV        ?= uv run
PNPM      ?= pnpm
ADVISOR   ?= local-advisor
TEST_DB   ?= postgresql+asyncpg://nevis:nevis@localhost:5434/nevis
OPENSPEC  ?= $(PNPM) dlx @fission-ai/openspec@1.9.0

.PHONY: help setup up down provision seed \
	fmt lint test test-web test-browser test-db-up test-db-down \
	test-integration coverage openapi openspec audit check \
	eval bench capacity capacity-full measure web smoke

help:
	@echo "Setup and run"
	@echo "  make setup             Install Python and web dependencies"
	@echo "  make up                Start Compose"
	@echo "  make down              Stop Compose (keeps volumes)"
	@echo "  make provision         Provision ADVISOR=$(ADVISOR)"
	@echo "  make seed              Seed the fictional corpus"
	@echo "  make web               Vite console on :5173"
	@echo
	@echo "Checks"
	@echo "  make lint              Ruff, mypy, and web lint"
	@echo "  make test              Python unit tests"
	@echo "  make test-web          Frontend unit tests with coverage"
	@echo "  make test-browser      Playwright console tests"
	@echo "  make test-integration  Python integration tests (needs test DB)"
	@echo "  make coverage          Combined Python coverage (needs test DB)"
	@echo "  make check             Host quality gates without Docker"
	@echo "  make smoke             Compose smoke path"
	@echo
	@echo "Measure (Compose must be up and seeded)"
	@echo "  make eval              search_eval"
	@echo "  make bench             search_warm_p95"
	@echo "  make capacity          repo_capacity (1k/10k)"
	@echo "  make capacity-full     repo_capacity (10k/100k, opt-in)"
	@echo "  make measure           seed + eval + bench + capacity"

setup:
	test -f .env || cp .env.example .env
	uv sync --all-groups
	corepack enable
	cd web && $(PNPM) install --frozen-lockfile

up:
	$(COMPOSE) up --build -d --wait

down:
	$(COMPOSE) down

provision:
	$(API) python scripts/provision_advisor.py $(ADVISOR)

seed:
	$(COMPOSE) exec -T -e NEVIS_SEED_URL=http://127.0.0.1:8000 \
		api python scripts/seed_preview.py

web:
	cd web && $(PNPM) dev

fmt:
	$(UV) ruff format .

lint:
	$(UV) ruff format --check .
	$(UV) ruff check .
	$(UV) mypy src
	cd web && $(PNPM) lint

test:
	$(UV) pytest tests/unit

test-web:
	cd web && $(PNPM) test:coverage

test-browser:
	$(UV) playwright install chromium
	$(UV) pytest tests/browser

test-db-up:
	$(COMPOSE) -f compose.yaml -f compose.test.yaml -p nevis-integration \
		up --build --wait postgres migrate

test-db-down:
	$(COMPOSE) -f compose.yaml -f compose.test.yaml -p nevis-integration down -v

test-integration:
	NEVIS_TEST_DATABASE_URL=$(TEST_DB) $(UV) pytest tests/integration

coverage:
	NEVIS_TEST_DATABASE_URL=$(TEST_DB) ./scripts/coverage.sh

openapi:
	$(UV) python scripts/export_openapi.py
	cd web && $(PNPM) generate:api
	git diff --exit-code -- openapi.json web/src/api.generated.ts

openspec:
	$(OPENSPEC) validate --all --strict

audit:
	$(UV) pip-audit --local --skip-editable --progress-spinner off

check: lint test test-web audit openapi openspec

eval:
	$(COMPOSE) exec -T -e NEVIS_EVALUATION_URL=http://127.0.0.1:8000 \
		api python scripts/evaluate_mixed_search.py

bench:
	$(API) python scripts/benchmark_search.py

capacity:
	$(API) python scripts/benchmark_repository_search.py

capacity-full:
	$(COMPOSE) exec -T \
		-e NEVIS_BENCHMARK_CLIENTS=10000 \
		-e NEVIS_BENCHMARK_DOCUMENTS=100000 \
		api python scripts/benchmark_repository_search.py

measure: seed eval bench capacity

smoke:
	./scripts/compose-smoke.sh
