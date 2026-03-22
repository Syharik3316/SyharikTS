#!/usr/bin/env bash
# Apply SQL migrations to PostgreSQL (Ubuntu Server / local).
# Usage:
#   export DATABASE_URL='postgresql+asyncpg://user:pass@127.0.0.1:5432/syharikts'
#   bash scripts/run_migrations.sh
# Or set PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE explicitly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MIGRATIONS_DIR="${PROJECT_ROOT}/backend/migrations"

if [[ ! -d "${MIGRATIONS_DIR}" ]]; then
  echo "Migrations directory not found: ${MIGRATIONS_DIR}" >&2
  exit 1
fi

# Derive psql connection from DATABASE_URL if PGDATABASE not set
if [[ -z "${PGDATABASE:-}" ]] && [[ -n "${DATABASE_URL:-}" ]]; then
  # Strip sqlalchemy driver prefix
  raw="${DATABASE_URL#postgresql+asyncpg://}"
  raw="${raw#postgresql://}"
  # user:pass@host:port/db
  if [[ "$raw" =~ ^([^:]+):([^@]+)@([^/:]+)(:([0-9]+))?/(.+)$ ]]; then
    export PGUSER="${BASH_REMATCH[1]}"
    export PGPASSWORD="${BASH_REMATCH[2]}"
    export PGHOST="${BASH_REMATCH[3]}"
    export PGPORT="${BASH_REMATCH[5]:-5432}"
    export PGDATABASE="${BASH_REMATCH[6]%%\?*}"
  else
    echo "Could not parse DATABASE_URL for psql. Set PGHOST, PGUSER, PGPASSWORD, PGDATABASE manually." >&2
    exit 1
  fi
fi

if [[ -z "${PGDATABASE:-}" ]]; then
  echo "Set DATABASE_URL or PGHOST/PGUSER/PGPASSWORD/PGDATABASE" >&2
  exit 1
fi

echo "Applying migrations from ${MIGRATIONS_DIR} to database ${PGDATABASE}@${PGHOST:-localhost}..."
for f in "${MIGRATIONS_DIR}"/*.sql; do
  [[ -f "$f" ]] || continue
  echo "  -> $(basename "$f")"
  psql -v ON_ERROR_STOP=1 -f "$f"
done
echo "Done."
