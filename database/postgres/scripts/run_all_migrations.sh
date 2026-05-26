#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LEGACY_SCRIPT="$SCRIPT_DIR/run_phase1_migrations.sh"

if [[ ! -f "$LEGACY_SCRIPT" ]]; then
  echo "[ERROR] Legacy migration runner not found: $LEGACY_SCRIPT"
  exit 1
fi

echo "[INFO] Running ALL migrations in db/postgres/01_migrations (deterministic filename order)."
echo "[INFO] Using preferred alias run_all_migrations.sh."
echo "[INFO] Delegating execution to legacy implementation run_phase1_migrations.sh for compatibility."

bash "$LEGACY_SCRIPT" "$@"

echo "[OK] All migrations completed via run_all_migrations.sh."
