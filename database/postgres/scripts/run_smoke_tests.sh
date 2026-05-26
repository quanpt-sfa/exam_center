#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/db_target.sh"

db_target_load "${1:-}"

ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
TESTS_DIR="$ROOT_DIR/05_tests"

shopt -s nullglob
test_files=("$TESTS_DIR"/*.sql)

if (( ${#test_files[@]} == 0 )); then
  echo "[ERROR] No smoke test files found in $TESTS_DIR"
  exit 1
fi

pass_count=0
db_target_print_summary

for test_file in "${test_files[@]}"; do
  test_name="$(basename "$test_file")"
  echo "[INFO] Running smoke test $test_name..."

  if [[ "$test_name" == "001_assert_database_exists.sql" ]]; then
    psql -d "$DB_MAINTENANCE_DATABASE" -v ON_ERROR_STOP=1 -v "db_name=$DB_NAME" -f "$test_file"
  else
    psql -d "$DB_NAME" -v ON_ERROR_STOP=1 -f "$test_file"
  fi

  pass_count=$((pass_count + 1))
  echo "[PASS] $test_name"
done

echo "[OK] Smoke tests completed: $pass_count passed, 0 failed."
