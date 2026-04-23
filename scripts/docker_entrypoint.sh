#!/bin/bash
# Docker entrypoint: wait for database, run migrations, then exec CMD.
# Used by both dev (docker-compose.yml) and prod (docker-compose.prod.yml).
set -e

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"

echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -q; do
  sleep 1
done

ALEMBIC_INI="${ALEMBIC_INI:-/app/alembic.ini}"
ALEMBIC_DIR="${ALEMBIC_DIR:-/app/migrations}"
MIGRATION_MAX_RETRIES="${MIGRATION_MAX_RETRIES:-5}"
MIGRATION_RETRY_SECONDS="${MIGRATION_RETRY_SECONDS:-2}"

if [ -f "$ALEMBIC_INI" ] && [ -d "$ALEMBIC_DIR" ]; then
  echo "Checking migration state..."
  set +e
  CURRENT_REV=$(uv run alembic -c "$ALEMBIC_INI" current 2>/dev/null | tail -n 1)
  HEAD_REV=$(uv run alembic -c "$ALEMBIC_INI" heads 2>/dev/null | tail -n 1)
  set -e

  if [ -n "$HEAD_REV" ]; then
    echo "Migration current: ${CURRENT_REV:-<none>}"
    echo "Migration head:    ${HEAD_REV}"
  fi

  echo "Running database migrations (upgrade head)..."
  ATTEMPT=1
  until uv run alembic -c "$ALEMBIC_INI" upgrade head; do
    if [ "$ATTEMPT" -ge "$MIGRATION_MAX_RETRIES" ]; then
      echo "Migration failed after ${ATTEMPT} attempts."
      exit 1
    fi
    echo "Migration attempt ${ATTEMPT} failed, retrying in ${MIGRATION_RETRY_SECONDS}s..."
    ATTEMPT=$((ATTEMPT + 1))
    sleep "$MIGRATION_RETRY_SECONDS"
  done
else
  echo "Skipping migrations: missing $ALEMBIC_INI or $ALEMBIC_DIR"
fi

echo "Database ready."
exec "$@"
