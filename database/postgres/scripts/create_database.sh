#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/db_target.sh"

db_target_load "${1:-}"
db_target_print_summary

echo "[INFO] Checking PostgreSQL connectivity at ${PGHOST}:${PGPORT} as ${PGUSER}..."
psql -d "$DB_MAINTENANCE_DATABASE" -v ON_ERROR_STOP=1 -c "SELECT 1;" >/dev/null

echo "[INFO] Checking whether database '$DB_NAME' exists..."
EXISTS=$(psql -d "$DB_MAINTENANCE_DATABASE" -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME';")

if [[ "${EXISTS// /}" == "1" ]]; then
  echo "[INFO] Database '$DB_NAME' already exists."
  exit 0
fi

echo "[INFO] Creating database '$DB_NAME'..."
psql -d "$DB_MAINTENANCE_DATABASE" -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"$DB_NAME\";"

echo "[OK] Database '$DB_NAME' created."
