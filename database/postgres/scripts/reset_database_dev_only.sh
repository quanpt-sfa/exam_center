#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/db_target.sh"

db_target_load
FORCE="${1:-}"

if [[ "$FORCE" != "--force" ]]; then
  echo "[ERROR] DEVELOPMENT ONLY: this script drops and recreates '$DB_NAME'."
  echo "[INFO] Re-run as: ./reset_database_dev_only.sh --force"
  exit 1
fi

db_target_print_summary
echo "[WARN] DEVELOPMENT ONLY: dropping and recreating '$DB_NAME'..."
psql -d "$DB_MAINTENANCE_DATABASE" -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();"
psql -d "$DB_MAINTENANCE_DATABASE" -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS \"$DB_NAME\";"
psql -d "$DB_MAINTENANCE_DATABASE" -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"$DB_NAME\";"

echo "[OK] DEVELOPMENT ONLY reset complete for '$DB_NAME'."
