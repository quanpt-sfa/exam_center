# DR-2 Environment and Secrets Contract

## 1. Scope and Safety Invariants

This document defines the deployment-readiness environment contract for:
- API runtime
- Worker runtime
- Database maintenance operations
- Frontend runtime/build
- UE2E and release verification

Safety invariants in this phase:
- Do not print or commit real secrets.
- Runtime DB role and maintenance DB role must remain separate.
- Maintenance credentials are only for migrations/smoke/setup/cleanup.
- API and worker runtime must use runtime DB credentials.
- No forbidden DELETE grants to exam_sys_app.
- No production deployment claim is made in DR-2.

## 2. Environment Resolution Notes

API runtime environment resolution:
- Preferred: EXAM_SYS_NEXT_ENV
- Fallback: APP_ENV
- Allowed values: development, test, staging, production

Worker runtime safety notes:
- Runtime settings validate role safety and test-flag misuse.
- Test-only DSN bypass flags are rejected in production runtime context.

## 3. API Runtime Contract

Required API runtime env vars:
- POSTGRES_HOST
- POSTGRES_PORT
- POSTGRES_DB
- POSTGRES_USER
- POSTGRES_PASSWORD
- POSTGRES_SSLMODE
- EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET
- EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET
- EXAM_SYS_NEXT_TOKEN_ALGORITHM
- EXAM_SYS_NEXT_ACCESS_TOKEN_EXPIRES_MINUTES
- EXAM_SYS_NEXT_REFRESH_TOKEN_EXPIRES_MINUTES
- EXAM_SYS_NEXT_CORS_ALLOWED_ORIGINS

Recommended API runtime env vars:
- EXAM_SYS_NEXT_ENV
- APP_ENV
- EXAM_SYS_NEXT_API_PREFIX
- EXAM_SYS_NEXT_API_TITLE
- EXAM_SYS_NEXT_VERSION
- EXAM_SYS_NEXT_REQUEST_TIMEOUT
- POSTGRES_CONNECT_TIMEOUT
- POSTGRES_POOL_MIN_SIZE
- POSTGRES_POOL_MAX_SIZE
- POSTGRES_POOL_TIMEOUT
- POSTGRES_POOL_MAX_IDLE
- AUTH_RATE_LIMIT_ENABLED
- AUTH_MAX_FAILED_ATTEMPTS
- AUTH_LOCKOUT_WINDOW_SECONDS
- AUTH_LOCKOUT_DURATION_SECONDS

Optional production secret vars (validated if set):
- EXAM_SYS_NEXT_SESSION_SECRET
- EXAM_SYS_NEXT_COOKIE_SECRET
- SESSION_SECRET
- SESSION_SECRET_KEY
- EXAM_SYS_NEXT_SIGNING_SECRET
- EXAM_SYS_NEXT_ENCRYPTION_SECRET
- EXAM_SYS_NEXT_ENCRYPTION_KEY

## 4. Worker Runtime Contract

Required worker runtime env vars:
- POSTGRES_HOST
- POSTGRES_PORT
- POSTGRES_DB
- POSTGRES_USER
- POSTGRES_PASSWORD
- POSTGRES_SSLMODE

Required worker loop control env vars (deployment baseline):
- WORKER_POLL_INTERVAL_SECONDS
- WORKER_IDLE_SLEEP_SECONDS
- WORKER_BATCH_SIZE
- WORKER_LEASE_SECONDS
- WORKER_MAX_RETRIES
- WORKER_RETRY_BACKOFF_SECONDS
- WORKER_LOG_LEVEL

Conditional required worker env vars:
- STUDENT_CAPTURE_SOURCE_DSN is required when STUDENT_CAPTURE_ADAPTER_MODE is one of:
  - PRODUCTION
  - LIVE
  - SOURCE_DSN

Test-only worker flags (must not be enabled in production):
- ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS
- ALLOW_TEXTBOX_SQL_APP_DB_DSN_FOR_TESTS
- WORKER_STOP_AFTER_IDLE_CYCLES

Additional worker runtime env vars in use:
- WORKER_ID
- WORKER_ID_PREFIX
- WORKER_RUN_ONCE
- WORKER_MAX_RETRY_BACKOFF_SECONDS
- DISPATCHER_SUBMISSION_ID
- DISPATCHER_SUBMISSION_IDS
- DISPATCHER_ACTOR_USER_ID
- DISPATCHER_WORKER_ID
- CAPTURE_WORKER_ID
- CAPTURE_WORKER_LEASE_SECONDS
- CAPTURE_WORKER_MAX_JOBS_PER_RUN
- CAPTURE_WORKER_MAX_DATASET_ROWS
- STUDENT_CAPTURE_ADAPTER_MODE
- STUDENT_CAPTURE_ALLOWED_SCHEMAS
- STUDENT_CAPTURE_ALLOWED_TABLES
- TEXTBOX_SQL_EXECUTOR_DSN
- TEXTBOX_SQL_ALLOWED_SCHEMAS
- TEXTBOX_SQL_STATEMENT_TIMEOUT_MS
- TEXTBOX_SQL_MAX_ROWS
- TEXTBOX_SQL_MAX_COLUMNS
- GRADING_WORKER_ID
- GRADING_WORKER_LEASE_SECONDS
- GRADING_WORKER_POLL_INTERVAL
- GRADING_WORKER_MAX_TASKS_PER_RUN
- GRADING_WORKER_MAX_COMPARISONS_PER_RUN
- GRADING_WORKER_MAX_SCORES_PER_RUN
- MD_IMPORT_WORKER_ID
- MD_IMPORT_WORKER_POLL_INTERVAL
- MD_IMPORT_WORKER_LEASE_SECONDS

## 5. Database Maintenance Contract

Required maintenance env vars:
- POSTGRES_MAINTENANCE_HOST
- POSTGRES_MAINTENANCE_PORT
- POSTGRES_MAINTENANCE_DB
- POSTGRES_MAINTENANCE_USER
- POSTGRES_MAINTENANCE_PASSWORD
- POSTGRES_MAINTENANCE_SSLMODE

Usage boundary:
- Maintenance credentials are for setup/migrations/smoke/cleanup only.
- Runtime API/worker must not execute with maintenance DB role.

## 6. Frontend Contract

Required frontend runtime/build env vars:
- VITE_API_BASE_URL

Frontend/Playwright and hybrid integration env vars in use:
- FRONTEND_BASE_URL
- API_BASE_URL
- UE2E_RUN_INTEGRATION
- UE2E_AUTH_MODE
- UE2E_OWNER_PERSONA
- UE2E_PYTHON
- UE2E_STUDENT_A_LOGIN
- UE2E_STUDENT_B_LOGIN

## 7. UE2E and Release Verification Contract

Required UE2E/release verification env vars:
- UE2E_RUN_INTEGRATION=1
- UE2E_AUTH_MODE=bearer
- FRONTEND_BASE_URL
- API_BASE_URL

Related integration runtime vars (when worker orchestration and seed helpers are used):
- EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1
- POSTGRES_HOST
- POSTGRES_PORT
- POSTGRES_DB
- POSTGRES_USER
- POSTGRES_PASSWORD
- POSTGRES_SSLMODE
- POSTGRES_MAINTENANCE_USER
- POSTGRES_MAINTENANCE_PASSWORD

## 8. Explicit Forbidden Settings

Forbidden for UE2E-3A closure mode:
- UE2E_AUTH_MODE=cookie

Forbidden for production runtime:
- ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS=1
- ALLOW_TEXTBOX_SQL_APP_DB_DSN_FOR_TESTS=1
- UE2E_RUN_INTEGRATION=1
- UE2E_AUTH_MODE=cookie

Forbidden operations:
- App-role cleanup/migrations with runtime user.
- Use of maintenance credentials for long-running API/worker runtime.
- Real passwords, DSNs, or tokens in docs and committed env files.

## 9. Placeholder Example Files

Root baseline placeholder example (legacy + shared shell defaults):
- .env.example

App-specific placeholder examples:
- backend/.env.example
- frontend/.env.example
- worker/.env.example

All examples must use placeholders only and no real secret values.

## 10. Validation Tooling

Optional safe checker:
- scripts/check_deployment_env.py

Checker behavior:
- Validates required env presence by mode:
  - api
  - worker
  - frontend
  - maintenance
  - ue2e
  - all
- Prints variable names with present/missing status only.
- Never prints secret values.
- Exits non-zero on missing required variables.
- Fails production mode when test-only flags are enabled.

## 11. DR-2 Evidence Notes

Preflight before DR-2 changes:
- python scripts/check_verification_report_heads.py: PASS
- python scripts/check_no_forbidden_weakening.py: PASS

Post-change verification in this phase:
- python scripts/check_verification_report_heads.py: PASS
- python scripts/check_no_forbidden_weakening.py: PASS

Deployment env checker execution (local shell evidence):
- python scripts/check_deployment_env.py --mode api: FAIL (expected not-ready)
  - missing EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET
  - missing EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET
  - missing EXAM_SYS_NEXT_TOKEN_ALGORITHM
  - missing EXAM_SYS_NEXT_ACCESS_TOKEN_EXPIRES_MINUTES
  - missing EXAM_SYS_NEXT_REFRESH_TOKEN_EXPIRES_MINUTES
  - missing EXAM_SYS_NEXT_CORS_ALLOWED_ORIGINS
- python scripts/check_deployment_env.py --mode worker: FAIL (expected not-ready)
  - missing WORKER_POLL_INTERVAL_SECONDS
  - missing WORKER_IDLE_SLEEP_SECONDS
  - missing WORKER_BATCH_SIZE
  - missing WORKER_LEASE_SECONDS
  - missing WORKER_MAX_RETRIES
  - missing WORKER_RETRY_BACKOFF_SECONDS
  - missing WORKER_LOG_LEVEL
- python scripts/check_deployment_env.py --mode maintenance: FAIL (expected not-ready)
  - missing POSTGRES_MAINTENANCE_DB
- python scripts/check_deployment_env.py --mode ue2e --allow-test-flags: FAIL (expected not-ready)
  - missing FRONTEND_BASE_URL
  - missing API_BASE_URL

Interpretation:
- DR-2 contract and checker are in place.
- Current shell is intentionally treated as not deployment-ready until missing vars are explicitly provided.
