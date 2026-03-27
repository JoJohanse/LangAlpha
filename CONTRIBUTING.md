# Contributing to LangAlpha

Thanks for your interest in contributing to LangAlpha! This guide covers how to set up your development environment and submit changes.

## Prerequisites

**Docker setup (recommended):**
- Docker and Docker Compose

**Manual setup:**
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker (for PostgreSQL and Redis)
- Node.js 22+ and pnpm (for the web UI)

See the [README](README.md#getting-started) for the Docker-based quick start.

## Manual Setup

If you prefer running services directly on your machine instead of Docker:

### 1. Clone and install

```bash
git clone https://github.com/ginlix-ai/langalpha.git
cd langalpha

# Install Python dependencies (includes dev + test deps)
uv sync --group dev --extra test

# Install frontend dependencies
cd web && pnpm install && cd ..

# Optional: install browser dependencies for web crawling
source .venv/bin/activate
scrapling install
```

### 2. Configure environment

```bash
cp .env.example .env
make config   # interactive wizard, or edit .env and agent_config.yaml manually
```

No keys are strictly required — see [Data Provider Fallback Chain](README.md#data-provider-fallback-chain). For the full experience, set `DAYTONA_API_KEY` and `FMP_API_KEY`. For LLM access, set an API key or connect via OAuth in the UI.

### 3. Start infrastructure

```bash
make setup-db   # starts PostgreSQL + Redis in Docker and runs migrations
```

### 4. Run the backend

```bash
make dev   # port 8000, with hot-reload
```

### 5. Run the frontend

```bash
make dev-web   # port 5173
```

### 6. Or use the CLI

```bash
ptc-agent              # interactive session
ptc-agent --plan-mode  # with plan approval
```

### Verify your setup

```bash
curl http://localhost:8000/health
# → {"status": "healthy"}
```

## Development Workflow

1. **Fork** the repository and clone your fork
2. **Set up** your environment following the [Getting Started](README.md#getting-started) guide
3. **Create a branch** for your change: `git checkout -b my-feature`
4. **Make your changes** — the backend supports hot-reload, so changes to `src/` take effect immediately
5. **Run tests** to verify nothing is broken:
   ```bash
   make test       # backend unit tests
   make test-web   # frontend unit tests
   make lint       # linters
   ```
6. **Commit** with a clear message describing the change
7. **Open a pull request** against `main`

## Code Style

**Python:**
- Linted with [Ruff](https://docs.astral.sh/ruff/) — run `uv run ruff check src/` to check
- Async-first: use `async def` for handlers and services
- No ORM — raw SQL via psycopg3

**Frontend (TypeScript/React):**
- Linted with ESLint 9 (flat config) — run `cd web && pnpm lint` to check
- Components use shadcn/ui + Tailwind CSS

## Tests

- **Unit tests must pass** before merging — these run in CI automatically
- **Integration tests are optional** locally — they require a running PostgreSQL instance and skip gracefully when API keys are absent
- Backend tests: `uv run pytest tests/unit/ -v`
- Frontend tests: `cd web && pnpm vitest run`

## Reporting Issues

Open a [GitHub Issue](https://github.com/ginlix-ai/langalpha/issues) with:
- What you expected vs what happened
- Steps to reproduce
- Relevant logs or screenshots

## Questions?

Open a [GitHub Discussion](https://github.com/ginlix-ai/langalpha/discussions) or comment on a relevant issue.
