# Worker Runtime Orchestration Developer Runbook

## Purpose
This runbook describes how to run, verify, and troubleshoot worker runtime orchestration roles (`dispatcher`, `capture`, `grading`) in local PostgreSQL integration workflows.

## Role Boundaries
- Runtime execution must use app role (`POSTGRES_USER`, typically `exam_sys_app`).
- Seed and cleanup must use maintenance role (`POSTGRES_MAINTENANCE_USER`, typically `postgres`).
- Keep runtime and maintenance credentials separate.

## Required Environment
Set runtime environment:

```powershell
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_DB = "exam_sys_dev"
$env:POSTGRES_USER = "exam_sys_app"
$env:POSTGRES_PASSWORD = "<runtime-password>"
$env:POSTGRES_SSLMODE = "prefer"
```

Set maintenance environment:

```powershell
$env:POSTGRES_MAINTENANCE_HOST = "localhost"
$env:POSTGRES_MAINTENANCE_PORT = "5432"
$env:POSTGRES_MAINTENANCE_USER = "postgres"
$env:POSTGRES_MAINTENANCE_PASSWORD = "<maintenance-password>"
```

Enable integration mode:

```powershell
$env:EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION = "1"
```

Recommended integration overrides for WRO pack:

```powershell
$env:ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS = "1"
$env:ALLOW_TEXTBOX_SQL_APP_DB_DSN_FOR_TESTS = "1"
$env:TEXTBOX_SQL_EXECUTOR_DSN = "host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app password=<runtime-password> sslmode=prefer"
```

## Run Smoke + WRO Integration Pack

```powershell
python worker/scripts/run_wro_postgres_integration.py --psql-path "<psql-path>"
```

What this command does:
- Validates required runtime and maintenance DB env vars.
- Runs smoke SQL [database/postgres/05_tests/279_assert_wro_runtime_ready.sql](database/postgres/05_tests/279_assert_wro_runtime_ready.sql).
- Runs PostgreSQL integration tests in [worker/tests/test_wro_runtime_postgres_integration.py](worker/tests/test_wro_runtime_postgres_integration.py).

## Run Individual Runtime Roles
Config validation:

```powershell
python worker/worker_runtime/cli.py config-check --role all
```

Dispatcher one-shot:

```powershell
python worker/worker_runtime/cli.py run-dispatcher --once --submission-id <exam_submission_id> --actor-user-id <user_id>
```

Capture one-shot (deterministic test adapter):

```powershell
python worker/worker_runtime/cli.py run-capture --once --allow-app-db-dsn-for-tests --use-deterministic-test-adapter
```

Grading one-shot:

```powershell
python worker/worker_runtime/cli.py run-grading --once
```

Run all roles one-shot in orchestration order:

```powershell
python worker/worker_runtime/cli.py run-all --once --roles dispatcher,capture,grading --dispatcher-submission-id <exam_submission_id> --dispatcher-actor-user-id <user_id> --allow-app-db-dsn-for-tests --use-deterministic-test-adapter
```

## Troubleshooting
- Missing env validation:
  - Confirm all `POSTGRES_*` and `POSTGRES_MAINTENANCE_*` variables are set.
- Capture worker cannot run deterministic adapter:
  - Ensure both `--allow-app-db-dsn-for-tests` and `--use-deterministic-test-adapter` are provided.
- Grading worker stalls in test mode:
  - Ensure `TEXTBOX_SQL_EXECUTOR_DSN` is present and reachable.
- Permission errors:
  - Confirm runtime role is app role and setup/cleanup is maintenance role.
- Redaction failures:
  - Inspect runtime logs and verify forbidden payload fields and secret tokens are not emitted.

## Operational Limitations
- Dispatcher runtime currently requires explicit submission IDs (`--submission-id` or env-based list) and does not perform automatic pending-submission scanning.
- Deterministic capture adapter is a test-only path and is not a production capture implementation.
- `run-all` executes roles in configured order and each role can be idle depending on queued work.
