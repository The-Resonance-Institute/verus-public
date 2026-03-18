.PHONY: help up down build logs shell test test-unit test-integration lint fmt migrate revision psql clean

COMPOSE := docker compose
PYTEST_OPTS ?= -q --tb=short
MIGRATION_MSG ?= migration

help:
	@echo "Verus — Development Commands"
	@echo ""
	@echo "  up               Start all services (postgres, localstack, api, worker)"
	@echo "  down             Stop all services"
	@echo "  build            Rebuild API image"
	@echo "  logs             Follow logs for all services"
	@echo "  shell            Open shell in running api container"
	@echo ""
	@echo "  test             Run full unit test suite"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests (requires running postgres)"
	@echo "  test-cov         Run tests with coverage report"
	@echo ""
	@echo "  lint             Run ruff linter"
	@echo "  fmt              Run black formatter"
	@echo ""
	@echo "  migrate          Apply all pending migrations (alembic upgrade head)"
	@echo "  revision         Create new migration (MIGRATION_MSG=description)"
	@echo "  psql             Open psql shell in postgres container"
	@echo ""
	@echo "  clean            Remove all containers and volumes"

up:
	$(COMPOSE) up -d
	@echo "Services starting. API at http://localhost:8000"

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build api worker

logs:
	$(COMPOSE) logs -f

shell:
	$(COMPOSE) exec api /bin/bash

test:
	python -m pytest tests/ -m "not integration" $(PYTEST_OPTS)

test-unit:
	python -m pytest tests/unit/ $(PYTEST_OPTS)

test-integration:
	python -m pytest tests/integration/ $(PYTEST_OPTS)

test-cov:
	python -m pytest tests/ -m "not integration" \
		--cov=packages \
		--cov-report=term-missing \
		--cov-report=html:coverage_html \
		$(PYTEST_OPTS)

lint:
	ruff check packages/ services/ tests/

fmt:
	black packages/ services/ tests/

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "$(MIGRATION_MSG)"

psql:
	$(COMPOSE) exec postgres psql -U verus -d verus

clean:
	$(COMPOSE) down -v --remove-orphans
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
