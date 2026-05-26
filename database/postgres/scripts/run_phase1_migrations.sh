#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/db_target.sh"

db_target_load "${1:-}"

ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
MIGRATIONS_DIR="$ROOT_DIR/01_migrations"

db_target_print_summary
EXISTS=$(psql -d "$DB_MAINTENANCE_DATABASE" -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME';")
if [[ "${EXISTS// /}" != "1" ]]; then
  echo "[ERROR] Target database '$DB_NAME' does not exist. Run the DB create command first, or run the LAN setup command."
  exit 1
fi

shopt -s nullglob
migration_files=("$MIGRATIONS_DIR"/*.sql)

if (( ${#migration_files[@]} == 0 )); then
  echo "[ERROR] No migration files found in $MIGRATIONS_DIR"
  exit 1
fi

echo "[INFO] Running Phase 1 migrations against '$DB_NAME'..."
for migration in "${migration_files[@]}"; do
  echo "[INFO] Applying $(basename "$migration")"
  psql -d "$DB_NAME" -v ON_ERROR_STOP=1 -f "$migration"
done

echo "[OK] Phase 1 migrations completed."
