.PHONY: setup validate test lint up down agents
setup:
	npm run setup
validate:
	node scripts/validate-repo.mjs
agents:
	node scripts/bootstrap-agents.mjs
up:
	docker compose -f compose.yaml up -d --build
down:
	docker compose -f compose.yaml down
test:
	uv run --locked --package datasoft-api pytest -q services/api/tests
	uv run --locked --package datasoft-ml pytest -q services/ml/tests
	npm run --prefix apps/web check
lint:
	uv run --locked ruff check services
	uv run --locked ruff format --check services
