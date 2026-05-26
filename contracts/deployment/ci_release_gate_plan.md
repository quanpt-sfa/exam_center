# DR-5 CI and Release Gate Hardening Plan

## 1. Scope and Safety Invariants

This phase audits CI gate coverage and hardens deployment-readiness workflows without adding any cloud deployment step.

Safety invariants applied in this phase:
- no deployment to cloud providers
- no secret values in workflow files
- no secret echo in job logs
- no weakening of auth or test guardrails
- no silent skip of critical gates
- browser UE2E remains manual-dispatch unless repository policy requires mandatory PR execution
- existing S2W workflows remain in place

## 2. Existing Workflow Coverage

Current workflows under `.github/workflows`:
- `api-ci.yml`
  - dependency install and runtime import sanity
  - API unit tests
  - PostgreSQL migrations and smoke tests
  - API + worker PostgreSQL integration tests
- `frontend-ci.yml`
  - frontend dependency install
  - frontend unit tests
  - frontend build
- `s2w-fast-regression.yml`
  - S2W/WRO fast unit and static regression packs
  - verification report head checker
  - no-forbidden-weakening checker
- `s2w-postgres-integration.yml`
  - S2W-5, S2W-6 PostgreSQL integration
  - WRO PostgreSQL integration (main/manual)
  - S2W-7 E2E integration (manual dispatch)
- `s2w4-worker-regression.yml`
  - S2W-4 unit/static regression
  - S2W-4 PostgreSQL integration regression

## 3. Missing or Weak Gates Identified

Gate audit against DR-5 target list:
- frontend unit/build: now covered in `frontend-ci.yml` as fast gate
- API tests: covered in `api-ci.yml`
- worker unit/static: covered by `s2w-fast-regression.yml` and `s2w4-worker-regression.yml`
- PostgreSQL integration: covered by `api-ci.yml`, `s2w4-worker-regression.yml`, and `s2w-postgres-integration.yml`
- browser UE2E: present as manual S2W-7 integration in `s2w-postgres-integration.yml` (not forced on every PR)
- DB smoke: covered in `api-ci.yml`; additionally hardened via DR-5 manual readiness workflow
- no-forbidden weakening: covered by `s2w-fast-regression.yml`; additionally executed in DR-5 manual readiness workflow

Primary hardening gap addressed in DR-5:
- no dedicated manual deployment-readiness workflow that documents optional DB gate behavior with explicit not-run reasons when secrets are absent.

## 4. Proposed Gating Levels

### 4.1 PR Fast Gate

Purpose:
- short-latency correctness and safety checks on pull requests.

Recommended coverage:
- `frontend-ci.yml` (npm ci, unit tests, build)
- `s2w-fast-regression.yml` (S2W/WRO unit-static + hardening checkers)
- selected `api-ci.yml` unit jobs

### 4.2 Main Branch Integration Gate

Purpose:
- deeper integration checks on `main`.

Recommended coverage:
- `api-ci.yml` PostgreSQL migrations/smoke + API integration tests
- `s2w4-worker-regression.yml` PostgreSQL integration regression
- `s2w-postgres-integration.yml` S2W-5/6 + WRO integration jobs

### 4.3 Manual Release Gate

Purpose:
- controlled release-readiness verification without deployment.

Workflow:
- `deployment-readiness-manual.yml` (workflow_dispatch)

Behavior:
- always runs hardening checkers
- runs optional DB integration only if explicitly requested and required secrets are available
- prints explicit not-run reasons when DB gate is not requested or secrets are missing

### 4.4 Optional Scheduled Gate

Purpose:
- periodic drift detection for integration health.

Policy suggestion:
- add a scheduled trigger only after runner budget and flake profile are approved.
- keep browser UE2E out of mandatory schedule unless stability target is met.

## 5. Required CI Secrets and Env Names (No Values)

For `deployment-readiness-manual.yml` optional DB gate:
- `CI_PG_HOST`
- `CI_PG_PORT`
- `CI_PG_DB`
- `CI_PG_RUNTIME_USER`
- `CI_PG_RUNTIME_PASSWORD`
- `CI_PG_MAINTENANCE_USER`
- `CI_PG_MAINTENANCE_PASSWORD`
- `CI_PG_SSLMODE`

Non-secret runtime env names set inside job from the secrets above:
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_SSLMODE`
- `POSTGRES_MAINTENANCE_HOST`
- `POSTGRES_MAINTENANCE_PORT`
- `POSTGRES_MAINTENANCE_DB`
- `POSTGRES_MAINTENANCE_USER`
- `POSTGRES_MAINTENANCE_PASSWORD`
- `POSTGRES_MAINTENANCE_SSLMODE`

## 6. Hosted CI Evidence Policy

Hosted CI pass policy:
- hosted pass can be claimed only with an observed run record
- required evidence includes workflow name, run ID, and run URL
- local execution evidence must not be represented as hosted CI pass evidence

Minimum evidence template:
- workflow: `<workflow-name>`
- run id: `<github-run-id>`
- run url: `<github-actions-run-link>`
- commit: `<sha>`
- conclusion: `success|failure|cancelled`

## 7. DR-5 Changes Applied in This Phase

Workflow changes:
- updated `frontend-ci.yml` to include `npm run build` in fast gate job
- added `deployment-readiness-manual.yml` with:
  - workflow_dispatch
  - required checkers
  - optional DB smoke gate conditioned on input + secret presence
  - explicit not-run reason steps

No changes made:
- no cloud deployment job added
- no existing S2W workflows removed
- no browser UE2E made mandatory on all PRs

## 8. Verification Notes for This Repository State

Local verification in this phase must include:
- `python scripts/check_verification_report_heads.py`
- `python scripts/check_no_forbidden_weakening.py`

YAML validation notes:
- no dedicated YAML linter tooling (`yamllint`/`actionlint`) was discovered in this repository snapshot
- workflow YAML files were reviewed manually for syntax and expression correctness

Hosted CI status note:
- this document does not claim hosted GitHub Actions pass without explicit run ID/link evidence.