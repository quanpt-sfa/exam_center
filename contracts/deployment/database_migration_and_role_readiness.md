# DR-3 Database Migration and Role Readiness

## 1. Scope and Invariants

This DR-3 document defines auditable database deployment readiness for migration execution, smoke verification, role separation, and release rehearsal commands.

Strict invariants:
- Do not grant forbidden DELETE permissions to exam_sys_app on capture/grading evidence tables.
- Do not weaken runtime-vs-maintenance role boundaries.
- Do not modify existing migrations unless a concrete migration-readiness defect is confirmed.
- Do not claim passes for commands not run.
- Do not expose passwords or DSNs.
- Worker/runtime paths must not depend on submission.answer_state.

## 2. Migration Directory Map

Primary directory:
- database/postgres/01_migrations

Observed migration coverage:
- 0001-0014: phase-1 foundations (roles, schemas, core grants/indexes/hardening)
- 0015-0027: assessment foundations
- 0028-0039: facility and delivery pre-session foundations
- 0040-0055: session and generated-instance layers
- 0056-0067: submission and capture foundations
- 0068-0078: phase 4.7 grading/capture modality foundations
- 0079-0089: phase 5A grading runtime tables and safe views
- 0090-0101: runtime lease, importing/ops, auth session/lockout, MD8, S2W3 dispatch outcome

Operational note:
- Migration runners execute files by deterministic filename order.
- Numeric prefix reuse exists (for example 0090_* and 0091_* appear in multiple files), so deployment rehearsal should always rely on full filename ordering, not numeric label alone.

## 3. Smoke SQL Directory Map

Primary directory:
- database/postgres/05_tests

Observed smoke coverage:
- 001-125: foundational schema/constraint/version checks
- 126-206: phase-4 and phase-4.7 readiness and safety checks
- 207-265: phase-5/5A runtime evidence and scoring pipeline checks
- 266-280: S2W/WRO/UE2E readiness checks

Known release-relevant smoke files:
- 276_assert_s2w5_capture_job_lease_schema_ready.sql
- 277_assert_s2w6_processing_status_read_model_ready.sql
- 278_assert_s2w7_e2e_prerequisites_ready.sql
- 279_assert_wro_runtime_ready.sql
- 280_assert_ue2e_auth_principals_ready.sql

Later smoke files after 280:
- None observed at this snapshot.

## 4. Required Release Order

Required execution order for DB release rehearsal:
1. Ensure database exists and maintenance connectivity is valid.
2. Apply migrations in deterministic full-filename order.
3. Run smoke SQL checks.
4. Run integration packs (S2W-5, S2W-6, S2W-7, WRO) as required by release scope.

Practical script chain (non-destructive):
- database/postgres/scripts/create_database.ps1 or create_database.sh
- database/postgres/scripts/run_phase1_migrations.ps1 or run_phase1_migrations.sh
- database/postgres/scripts/run_smoke_tests.ps1 or run_smoke_tests.sh
- worker/scripts/run_s2w5_postgres_integration.py
- worker/scripts/run_s2w6_postgres_integration.py
- worker/scripts/run_s2w7_e2e_integration.py
- worker/scripts/run_wro_postgres_integration.py

## 5. Role Model Readiness

Runtime role:
- POSTGRES_USER=exam_sys_app
- Used by API and worker runtime execution paths.

Maintenance role:
- POSTGRES_MAINTENANCE_USER=postgres (or approved maintenance deployment role)
- Used for migrations, smoke runs, setup/cleanup only.

Test-only setup/cleanup role usage:
- Integration packs and test supports use maintenance credentials for targeted cleanup where runtime role intentionally lacks DELETE permissions on protected evidence tables.

Boundary rule:
- Runtime workers/API must never run as maintenance role.

## 6. Forbidden Grants and Guardrails

Forbidden grant policy:
- No DELETE grants to exam_sys_app on capture/grading evidence tables, including protected tables checked by scripts/check_no_forbidden_weakening.py.

Guard command:
- python scripts/check_no_forbidden_weakening.py

Current posture:
- Guard checker passed in preflight and post-change verification for this DR-3 phase.

## 7. Backup and Rollback Guidance

Backup-before-migration guidance:
- Take backup before applying migrations in any non-dev environment.
- Prefer maintenance role for backup/restore operations.

PowerShell backup example (placeholder paths):
- & "<pg_dump-path>" -h $env:POSTGRES_MAINTENANCE_HOST -p $env:POSTGRES_MAINTENANCE_PORT -U $env:POSTGRES_MAINTENANCE_USER -d $env:POSTGRES_MAINTENANCE_DB -F c -f "<backup-output-path>"

Rollback strategy:
- Restore-based rollback unless explicit, validated down-migration scripts exist.
- No assumption of reversible down migrations is made in this phase.

Production safety rule:
- Do not run reset_database_dev_only.ps1/.sh on production or hosted release databases.

## 8. Release DB Checklist

Connectivity checks:
- Runtime role connectivity (exam_sys_app) succeeds.
- Maintenance role connectivity succeeds.

Migration/smoke checks:
- Migrations applied successfully.
- Release-relevant smokes pass (276, 277, 278, 279, 280).
- Later smoke files (if added) are included and pass.

Hardening checks:
- python scripts/check_no_forbidden_weakening.py passes.
- python scripts/check_verification_report_heads.py passes.

Runtime boundary checks:
- No maintenance-role runtime loops.
- No test-only flags in production mode.

## 9. Windows PowerShell Local Release Rehearsal Commands

The commands below are local rehearsal commands and do not claim production deployment.

1) Set maintenance/runtime env placeholders:

```powershell
$env:POSTGRES_HOST="127.0.0.1"
$env:POSTGRES_PORT="5432"
$env:POSTGRES_DB="exam_sys_dev"
$env:POSTGRES_USER="exam_sys_app"
$env:POSTGRES_PASSWORD="<runtime-password>"
$env:POSTGRES_SSLMODE="prefer"

$env:POSTGRES_MAINTENANCE_HOST="127.0.0.1"
$env:POSTGRES_MAINTENANCE_PORT="5432"
$env:POSTGRES_MAINTENANCE_DB="exam_sys_dev"
$env:POSTGRES_MAINTENANCE_USER="postgres"
$env:POSTGRES_MAINTENANCE_PASSWORD="<maintenance-password>"
$env:POSTGRES_MAINTENANCE_SSLMODE="prefer"
```

2) Connectivity checks (no password echo):

```powershell
$env:PGPASSWORD=$env:POSTGRES_MAINTENANCE_PASSWORD
& "<psql-path>" -h $env:POSTGRES_MAINTENANCE_HOST -p $env:POSTGRES_MAINTENANCE_PORT -U $env:POSTGRES_MAINTENANCE_USER -d postgres -v ON_ERROR_STOP=1 -c "SELECT current_user, current_database();"

$env:PGPASSWORD=$env:POSTGRES_PASSWORD
& "<psql-path>" -h $env:POSTGRES_HOST -p $env:POSTGRES_PORT -U $env:POSTGRES_USER -d $env:POSTGRES_DB -v ON_ERROR_STOP=1 -c "SELECT current_user, current_database();"
```

3) Database create/migration/smoke baseline:

```powershell
.\db\postgres\scripts\create_database.ps1 -DatabaseName $env:POSTGRES_MAINTENANCE_DB
.\db\postgres\scripts\run_phase1_migrations.ps1 -DatabaseName $env:POSTGRES_MAINTENANCE_DB
.\db\postgres\scripts\run_smoke_tests.ps1 -DatabaseName $env:POSTGRES_MAINTENANCE_DB
```

4) Release-focused smoke runner:

```powershell
python scripts/run_db_release_smokes.py --psql-path "<psql-path>"
```

5) Integration packs and hardening gates:

```powershell
python worker/scripts/run_s2w5_postgres_integration.py --psql-path "<psql-path>"
python worker/scripts/run_s2w6_postgres_integration.py --psql-path "<psql-path>"
python worker/scripts/run_s2w7_e2e_integration.py --psql-path "<psql-path>"
python worker/scripts/run_wro_postgres_integration.py --psql-path "<psql-path>"
python scripts/check_verification_report_heads.py
python scripts/check_no_forbidden_weakening.py
```

## 10. Not-Claimed Items

This DR-3 document does not claim:
- Production database migration execution.
- Hosted database migration validation.
- Hosted CI/cloud database verification beyond explicitly cited local evidence in referenced reports.

## 11. Optional Release Smoke Runner (Added)

Added tool:
- scripts/run_db_release_smokes.py

Behavior:
- Accepts --psql-path.
- Uses environment variables for connection.
- Runs release smoke files in deterministic order:
  - 276, 277, 278, 279, 280 (if present)
  - then any smoke files with numeric prefix greater than 280.
- Prints pass/fail per smoke file.
- Never prints password values.
- Fails fast if psql is unavailable.
- Does not invoke any destructive reset scripts.

## 12. DR-3 Verification Evidence (This Session)

Executed commands:
- python scripts/check_verification_report_heads.py
- python scripts/check_no_forbidden_weakening.py
- python scripts/run_db_release_smokes.py --psql-path "<psql-path>"

Observed results:
- verification-head checker: PASS
- no-forbidden-weakening checker: PASS
- release smoke runner: PASS
  - 276_assert_s2w5_capture_job_lease_schema_ready.sql
  - 277_assert_s2w6_processing_status_read_model_ready.sql
  - 278_assert_s2w7_e2e_prerequisites_ready.sql
  - 279_assert_wro_runtime_ready.sql
  - 280_assert_ue2e_auth_principals_ready.sql
