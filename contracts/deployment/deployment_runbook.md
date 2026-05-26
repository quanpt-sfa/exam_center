# DR-6 Deployment Runbook and Operations Checklist

## 1. Scope and Non-Claims

This runbook is an operator-facing release procedure for this repository.

Scope:
- release from a verified commit
- operational startup/shutdown order
- smoke verification and rollback procedure

Non-claims:
- this document does not claim any actual production deployment execution
- this document does not include provider-specific deployment commands not already present in this repository

Safety invariants:
- never place real secrets in commands, logs, screenshots, or reports
- do not run maintenance cleanup using runtime app role
- do not expose bearer tokens or raw answer data in evidence
- do not use destructive reset scripts for production release databases

## 2. Release Inputs

Complete these inputs before release start:

| Input | Required | Example format | Notes |
|---|---|---|---|
| Commit SHA | yes | `ed4e43b8da8c65ce54f10b2cf0c268b6f860b22c` | Must match the reviewed/approved commit. |
| Artifact version | yes | `exam-sys-api:<version>` / `frontend-build-<version>` | Use your internal artifact naming policy. |
| Database backup reference | yes | `backup/exam_sys_dev_pre_release_<timestamp>.dump` | Backup must be taken before migration/smoke steps. |
| Migration checklist | yes | `database/postgres/01_migrations` + `database/postgres/05_tests` verified | Track migration and smoke readiness explicitly. |
| Env/secrets readiness | yes | env contract checklist complete | Validate with DR-2 contract and secure secret store. |

Release input checklist:
- approved commit SHA is frozen
- artifact versions are recorded
- backup reference is recorded and restorable
- migration checklist is reviewed
- env/secrets contract is complete (without printing values)

## 3. Pre-Release Gates

Run all required gates and record evidence.

### 3.1 Required checkers

```powershell
python scripts/check_verification_report_heads.py
python scripts/check_no_forbidden_weakening.py
```

### 3.2 Frontend test/build gate

```powershell
Set-Location frontend
npm ci
npm run test -- --run
npm run build
```

### 3.3 API tests gate

```powershell
Set-Location ../..
python -m pytest -q backend/tests
```

### 3.4 Worker guardrails gate

```powershell
python worker/scripts/run_s2w4_unit_regression.py
python worker/scripts/run_s2w5_unit_regression.py
python -m pytest -q worker/tests/test_worker_runtime_settings.py worker/tests/test_worker_runtime_no_mutable_answer_source_guard.py
```

### 3.5 DB smoke gate

```powershell
python scripts/run_db_release_smokes.py --psql-path "<psql-path>"
```

### 3.6 UE2E 4/4 gate

Required outcome: all four checks pass with explicit evidence.

Expected UE2E checks:
- login/auth flow check
- processing-status visibility check
- submission result page check
- no-owner-access enforcement check

Suggested execution path:

```powershell
python worker/scripts/run_s2w7_e2e_integration.py --psql-path "<psql-path>"
Set-Location frontend
npm run e2e
```

Evidence rule:
- mark UE2E gate passed only when 4/4 checks are observed in logs/reports

## 4. Startup Order (Release Sequence)

Perform startup in this order:
1. database availability and role connectivity
2. migrations and DB smoke checks
3. API startup and health checks
4. worker runtime startup (dispatcher/capture/grading)
5. frontend startup or static preview serving

Mandatory boundary:
- use maintenance role only for migration/smoke/setup operations
- use runtime app role for API/worker runtime operations

## 5. API Startup

### 5.1 Command template

```powershell
Set-Location backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 5.2 Environment template (placeholder only)

```powershell
$env:EXAM_SYS_NEXT_ENV="staging"
$env:APP_ENV="staging"
$env:POSTGRES_HOST="<db-host>"
$env:POSTGRES_PORT="5432"
$env:POSTGRES_DB="<db-name>"
$env:POSTGRES_USER="exam_sys_app"
$env:POSTGRES_PASSWORD="<runtime-password>"
$env:POSTGRES_SSLMODE="prefer"
$env:EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET="<access-secret>"
$env:EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET="<refresh-secret>"
$env:EXAM_SYS_NEXT_TOKEN_ALGORITHM="HS256"
$env:EXAM_SYS_NEXT_ACCESS_TOKEN_EXPIRES_MINUTES="15"
$env:EXAM_SYS_NEXT_REFRESH_TOKEN_EXPIRES_MINUTES="10080"
$env:EXAM_SYS_NEXT_CORS_ALLOWED_ORIGINS="<frontend-origin>"
```

### 5.3 Health check template

```powershell
curl.exe http://127.0.0.1:8000/api/v1/health
curl.exe http://127.0.0.1:8000/api/v1/db-health
```

Pass criteria:
- health endpoint responds successfully
- db-health endpoint confirms DB connectivity

## 6. Worker Runtime Startup

Run from worker module directory:

```powershell
Set-Location worker
```

### 6.1 Config check

```powershell
python -m worker_runtime.cli config-check --role all
```

When to use:
- always run before starting worker loops
- confirms sanitized config and role safety constraints

### 6.2 Dispatcher loop

```powershell
python -m worker_runtime.cli run-dispatcher --worker-id dispatcher-01
```

When to use:
- dispatch-only runtime operation
- queueing/dispatch orchestration checks

### 6.3 Capture loop

```powershell
python -m worker_runtime.cli run-capture --worker-id capture-01
```

When to use:
- capture pipeline runtime operation
- source ingestion and capture evidence flow

### 6.4 Grading loop

```powershell
python -m worker_runtime.cli run-grading --worker-id grading-01
```

When to use:
- grading pipeline runtime operation
- score/result materialization flow

### 6.5 Combined loop

```powershell
python -m worker_runtime.cli run-all --roles dispatcher,capture,grading
```

When to use:
- controlled combined orchestration runtime loop
- useful for bounded release rehearsal environments

Production safety note:
- do not enable test-only flags (`--allow-app-db-dsn-for-tests`, `--use-deterministic-test-adapter`, `--allow-test-scaffold-services`) in production runtime

## 7. Frontend Startup and Build

### 7.1 Install/build commands

```powershell
Set-Location frontend
npm ci
npm run build
```

Alternative (local non-CI install):

```powershell
npm install
```

### 7.2 Runtime API base URL

Required env:

```powershell
$env:VITE_API_BASE_URL="http://127.0.0.1:8000"
```

### 7.3 Preview/static serving notes

Preview command:

```powershell
npm run preview -- --host 127.0.0.1 --port 5173
```

Notes:
- use preview/static serving for release verification
- confirm `VITE_API_BASE_URL` points to the intended API endpoint before smoke checks

## 8. Post-Deploy Smoke Checklist

Run smoke checks immediately after startup sequence.

Required checks:
- login/auth check
- processing-status API check
- submission result page check
- no-owner-access check
- redaction/no raw answer exposure check

Command templates:

```powershell
# API auth/health baseline (no token values in output evidence)
curl.exe http://127.0.0.1:8000/api/v1/health
curl.exe http://127.0.0.1:8000/api/v1/db-health

# Processing-status and access-policy focused tests
python -m pytest -q backend/tests/test_processing_status_api_unit.py backend/tests/test_submission_access_policy_unit.py

# Frontend submission/result/no-owner-access checks
Set-Location frontend
npm run e2e
```

Redaction rule for smoke evidence:
- do not include raw answer data, bearer tokens, authorization headers, or secret env values

## 9. Rollback Procedure

Rollback sequence:
1. stop new worker intake loops (dispatcher/capture/grading)
2. preserve current database state for investigation
3. restore backup only when migration rollback is required
4. revert application artifact to last known good version
5. re-run required smoke checks

Detailed operator guidance:
- do not run destructive reset scripts on release databases
- perform DB restore using maintenance role only
- keep runtime app role for application runtime, not maintenance cleanup
- confirm post-rollback health (`/api/v1/health`, `/api/v1/db-health`) before reopening traffic

## 10. Incident Notes and Triage

### 10.1 Worker stuck jobs

Symptoms:
- queue not draining
- repeated idle cycles with pending work

Actions:
- run `config-check --role all`
- run role-specific `--once` command to isolate behavior
- verify DB role and lease configuration

### 10.2 Failed capture

Symptoms:
- capture claims not progressing
- capture jobs retried repeatedly

Actions:
- verify capture source DSN/env contract
- verify capture worker role configuration and lease settings
- avoid enabling test-only capture flags in production

### 10.3 Failed grading

Symptoms:
- grading tasks remain pending or fail repeatedly

Actions:
- validate grading runtime env and poll/lease settings
- run focused grading loop with `--once` for controlled debugging
- confirm no forbidden grant/security regressions using checkers

### 10.4 DB permission errors

Symptoms:
- runtime errors on table access or writes

Actions:
- verify runtime role is `exam_sys_app` for API/worker runtime
- verify maintenance role is used only for migration/smoke/setup
- run hardening gates to ensure no forbidden weakening drift

### 10.5 Frontend API base URL mismatch

Symptoms:
- frontend calls wrong API host/path
- login or submission views fail despite healthy backend

Actions:
- verify `VITE_API_BASE_URL`
- rebuild frontend artifact after env correction
- rerun frontend smoke/E2E checks

## 11. Evidence Template

Record each command using this template:

| Command | Result | Timestamp (ISO8601) | Operator | Log path | Not-run reason |
|---|---|---|---|---|---|
| `python scripts/check_verification_report_heads.py` | passed | 2026-05-13T00:00:00+07:00 | operator_a | logs/release/checkers.log | |
| `npm run e2e` | not-run | 2026-05-13T00:10:00+07:00 | operator_a | logs/release/frontend-e2e.log | frontend preview server unavailable |

Rules:
- never mark `not-run` as `passed`
- include explicit reason when a gate is not run
- include path to redacted evidence log

## 12. Security Notes

Mandatory security controls:
- no secrets in logs, docs, screenshots, or command examples
- no tokens in screenshots or shared terminal captures
- no raw SQL answers or raw answer payloads in reports
- maintain strict runtime vs maintenance DB role separation

Additional guardrails:
- run `check_verification_report_heads.py` and `check_no_forbidden_weakening.py` before and after release rehearsal
- keep UE2E in bearer mode for closure gates
- reject production procedures that require destructive database reset

## 13. Related Deployment-Readiness Documents

- `contracts/deployment/env_and_secrets_contract.md`
- `contracts/deployment/database_migration_and_role_readiness.md`
- `contracts/deployment/local_release_rehearsal_command_pack.md`
- `contracts/deployment/ci_release_gate_plan.md`
