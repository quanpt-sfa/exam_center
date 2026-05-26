#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE_ARG="${1:-}"

bash "$SCRIPT_DIR/create_database.sh" "$ENV_FILE_ARG"
bash "$SCRIPT_DIR/run_all_migrations.sh" "$ENV_FILE_ARG"
