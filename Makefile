.PHONY: help configup down clean dev dev-web install test test-sandbox test-web test-all lint setup-db migrate docker-test-backend docker-test-web docker-test-all docker-build-test docker-phase1-backend docker-phase1-web docker-phase1-check

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

config: ## Interactive setup wizard (LLM, data, sandbox, search)
	@bash scripts/configure.sh
# ---------------------------------------------------------------------------
# Docker Compose (full-stack)
# ---------------------------------------------------------------------------
up: _sandbox-prepare ## Start full stack (PROVIDER=docker|daytona)
	SANDBOX_PROVIDER=$(PROVIDER) docker compose up --build

down: ## Stop all Docker Compose services
	docker compose down

clean: down ## Stop everything and remove stale sandbox containers
	@echo "Removing stale sandbox containers..."
	@docker rm -f $$(docker ps -aq --filter "name=langalpha-sandbox") 2>/dev/null || true
	@echo "Clean."

# Build sandbox image only when provider needs it (docker)
_sandbox-prepare:
ifeq ($(PROVIDER),docker)
	@echo "Building sandbox image for docker provider..."
	docker build -f Dockerfile.sandbox -t langalpha-sandbox:latest .
endif

# ---------------------------------------------------------------------------
# Manual development (without Docker for backend/frontend)
# ---------------------------------------------------------------------------
install: ## Install all dependencies (backend + frontend)
	uv sync --group dev --extra test
	cd web && pnpm install

dev: ## Start backend with hot-reload (requires DB + Redis running)
	uv run python server.py --reload

dev-web: ## Start frontend dev server
	cd web && pnpm dev

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------
test: ## Run backend unit tests
	uv run pytest tests/unit/ -v --tb=short

test-sandbox: _sandbox-prepare ## Run sandbox integration tests (PROVIDER=memory|docker|daytona)
	SANDBOX_TEST_PROVIDER=$(PROVIDER) uv run pytest tests/integration/sandbox/ -v --tb=short

test-web: ## Run frontend unit tests
	cd web && pnpm vitest run

test-all: test test-web ## Run all tests (backend + frontend)
	$(MAKE) test-sandbox PROVIDER=memory

# ---------------------------------------------------------------------------
# Linting
# ---------------------------------------------------------------------------
lint: ## Run all linters (Ruff + ESLint)
	uv run ruff check src/
	cd web && pnpm lint

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
setup-db: ## Start PostgreSQL + Redis in Docker and initialize tables
	./scripts/start_db.sh

migrate: ## Run database migrations
	uv run alembic upgrade head

# ---------------------------------------------------------------------------
# Dockerized test workflow (matches docker-compose deployment)
# ---------------------------------------------------------------------------
docker-build-test: ## Build backend image with test deps (pytest) enabled
	INCLUDE_DEV_DEPS=1 docker compose build backend

docker-test-backend: docker-build-test ## Run backend tests inside backend container
	INCLUDE_DEV_DEPS=1 docker compose run --rm backend uv run pytest tests/unit/ -v --tb=short

docker-test-web: ## Run frontend tests inside frontend container
	docker compose run --rm frontend sh -lc "npm install -g pnpm@10 && pnpm install --frozen-lockfile && pnpm vitest run"

docker-test-all: docker-test-backend docker-test-web ## Run backend + frontend tests via docker compose

# ---------------------------------------------------------------------------
# Phase 1 MVP closure regression (events + market-data-events + frontend closure)
# ---------------------------------------------------------------------------
docker-phase1-backend: docker-build-test ## Run phase1 backend regression tests in Docker
	INCLUDE_DEV_DEPS=1 docker compose run --rm -v ./tests:/app/tests backend uv run pytest -q \
		tests/unit/server/app/test_events.py \
		tests/unit/server/app/test_market_data_events.py

docker-phase1-web: ## Run phase1 frontend regression tests in Docker
	docker compose run --rm frontend_test "corepack enable && pnpm install --frozen-lockfile && pnpm vitest run \
		src/pages/Dashboard/components/__tests__/HotEventsCard.test.tsx \
		src/pages/Dashboard/__tests__/Dashboard.eventDeepLink.test.tsx \
		src/pages/MarketView/utils/__tests__/navigation.test.ts"

docker-phase1-check: docker-phase1-backend docker-phase1-web ## Run full phase1 closure regression in Docker
