#!/usr/bin/env bash
set -euo pipefail

db_target_repo_root() {
  local dir="${1:-$(pwd)}"
  while [[ "$dir" != "/" ]]; do
    if [[ -d "$dir/.git" ]]; then
      printf '%s\n' "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  echo "[ERROR] Could not resolve repository root." >&2
  return 1
}

db_target_load_env_file() {
  local env_file="$1"
  if [[ ! -f "$env_file" ]]; then
    echo "[ERROR] DB target env file not found: $env_file" >&2
    return 1
  fi

  while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    local line="${raw_line#"${raw_line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "$line" || "${line:0:1}" == "#" || "$line" != *"="* ]] && continue
    local key="${line%%=*}"
    local value="${line#*=}"
    key="${key//[[:space:]]/}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    export "$key=$value"
  done < "$env_file"
}

db_target_required() {
  local name="$1"
  local value="${!name:-}"
  if [[ -z "$value" ]]; then
    echo "[ERROR] Missing required DB target variable $name in .env.lan" >&2
    return 1
  fi
  if [[ "$value" =~ ^[[:space:]]*(\<[^>]+\>|changeme|change-me|placeholder|todo|set-locally)[[:space:]]*$ ]]; then
    echo "[ERROR] DB target variable $name is still a placeholder" >&2
    return 1
  fi
}

db_target_database_from_url() {
  local url="$1"
  if [[ "$url" =~ ^postgres(ql)?://[^/]+/([^?]+) ]]; then
    printf '%s\n' "${BASH_REMATCH[2]}"
    return 0
  fi
  echo "[ERROR] DATABASE_URL must use postgres:// or postgresql:// and include a database name." >&2
  return 1
}

db_target_load() {
  local explicit_env_file="${1:-}"
  local script_dir
  script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[1]}")" && pwd)"
  local repo_root
  repo_root="$(db_target_repo_root "$script_dir")"
  DB_TARGET_ENV_FILE="${explicit_env_file:-${ENV_FILE:-$repo_root/.env.lan}}"
  if [[ "$DB_TARGET_ENV_FILE" != /* ]]; then
    DB_TARGET_ENV_FILE="$repo_root/$DB_TARGET_ENV_FILE"
  fi

  db_target_load_env_file "$DB_TARGET_ENV_FILE"

  db_target_required DB_HOST
  db_target_required DB_PORT
  db_target_required DB_USER
  db_target_required DB_PASSWORD
  db_target_required DB_NAME

  if [[ ! "$DB_NAME" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "[ERROR] DB_NAME must match ^[A-Za-z_][A-Za-z0-9_]*$" >&2
    return 1
  fi
  case "${DB_NAME,,}" in
    postgres|template0|template1)
      echo "[ERROR] DB_NAME must not be a maintenance database ($DB_NAME)" >&2
      return 1
      ;;
  esac

  if [[ -n "${POSTGRES_DB:-}" && "$POSTGRES_DB" != "$DB_NAME" ]]; then
    echo "[ERROR] POSTGRES_DB must match DB_NAME in $DB_TARGET_ENV_FILE" >&2
    return 1
  fi
  if [[ -n "${PGDATABASE:-}" && "$PGDATABASE" != "$DB_NAME" ]]; then
    echo "[ERROR] PGDATABASE must match DB_NAME in $DB_TARGET_ENV_FILE" >&2
    return 1
  fi
  if [[ -n "${DATABASE_URL:-}" ]]; then
    local url_db
    url_db="$(db_target_database_from_url "$DATABASE_URL")"
    if [[ "$url_db" != "$DB_NAME" ]]; then
      echo "[ERROR] DATABASE_URL database name must match DB_NAME" >&2
      return 1
    fi
  fi

  DB_SSLMODE="${DB_SSLMODE:-${POSTGRES_SSLMODE:-prefer}}"
  DB_MAINTENANCE_DATABASE="${DB_MAINTENANCE_DATABASE:-postgres}"
  case "${DB_MAINTENANCE_DATABASE,,}" in
    postgres|template0|template1) ;;
    *)
      echo "[ERROR] DB_MAINTENANCE_DATABASE must be postgres, template0, or template1" >&2
      return 1
      ;;
  esac

  export PGHOST="$DB_HOST"
  export PGPORT="$DB_PORT"
  export PGUSER="$DB_USER"
  export PGPASSWORD="$DB_PASSWORD"
}

db_target_print_summary() {
  echo "[INFO] DB target source: $DB_TARGET_ENV_FILE"
  echo "[INFO] DB target: host=$DB_HOST port=$DB_PORT user=$DB_USER db=$DB_NAME"
  echo "[INFO] Maintenance database: $DB_MAINTENANCE_DATABASE"
}
