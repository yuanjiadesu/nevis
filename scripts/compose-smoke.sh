#!/usr/bin/env sh
set -eu

docker compose up --build --wait
docker compose exec -T api python -c "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8000/health/ready').status == 200"
docker compose exec -T api python scripts/provision_advisor.py compose-smoke-advisor
docker compose exec -T api python scripts/verify_foundation.py
docker compose exec -T api python scripts/verify_ingestion.py
docker compose exec -T api python scripts/verify_search.py
docker compose exec -T api python scripts/evaluate_mixed_search.py
docker compose down
