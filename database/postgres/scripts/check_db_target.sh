#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/db_target.sh"

db_target_load
echo "[OK] DB target contract is valid."
db_target_print_summary
