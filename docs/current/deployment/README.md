---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# Deployment

Purpose: route deployment and runtime-operations work to the narrowest current runbook.

Current status:

- Deployment docs describe the FastAPI/PostgreSQL runtime.
- Release and setup guidance lives in `contracts/deployment/**`.

Current source paths:

- `contracts/deployment/deployment_runbook.md`
- `contracts/deployment/ci_release_gate_plan.md`
- `contracts/deployment/lan_deployment_readiness_plan.md`

Current commands:

- API startup: `cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- Frontend build: `cd frontend && npm run build`
- DB target check: `database/postgres/scripts/check_db_target.sh`

| Area | Source doc | Read first | Command if known | Status |
|---|---|---|---|---|
| `local-dev` | `contracts/deployment/deployment_runbook.md` | `contracts/deployment/deployment_runbook.md` | `cd frontend && npm run build` | `current` |
| `runtime-env` | `contracts/deployment/env_and_secrets_contract.md` | `contracts/deployment/env_and_secrets_contract.md` | `unknown` | `current` |
| `database setup` | `contracts/deployment/database_migration_and_role_readiness.md` | `contracts/deployment/database_migration_and_role_readiness.md` | `database/postgres/scripts/check_db_target.sh` | `current` |
| `API startup` | `contracts/deployment/deployment_runbook.md` | `contracts/deployment/deployment_runbook.md` | `cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` | `current` |
| `worker runtime` | `contracts/worker/worker_runtime_dev_runbook.md` | `contracts/worker/worker_runtime_dev_runbook.md` | `python worker/worker_runtime/cli.py config-check --role all` | `current` |
| `release gates` | `contracts/deployment/ci_release_gate_plan.md` | `contracts/deployment/ci_release_gate_plan.md` | `unknown` | `current` |
| `LAN deployment` | `contracts/deployment/lan_deployment_readiness_plan.md` | `contracts/deployment/lan_deployment_readiness_plan.md` | `unknown` | `current` |
| `troubleshooting` | `contracts/deployment/deployment_runbook.md` | `contracts/deployment/deployment_runbook.md` | `unknown` | `current` |

What this doc does not cover:

- Detailed API schemas
- Feature-level UX behavior
- Full worker command coverage

Read-first links:

- `docs/current/runtime/postgres.md`
- `docs/current/runtime/api.md`
- `docs/current/runtime/worker.md`
