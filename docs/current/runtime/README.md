---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# Runtime

Purpose: entrypoint for the current runtime docs.

Current status:

- Backend runtime: `backend/**`
- Database runtime: `database/postgres/**`
- Frontend runtime: `frontend/**`
- Worker runtime: `worker/**`

Current source paths:

- `backend/README.md`
- `frontend/README.md`
- `database/postgres/README.md`
- `contracts/worker/worker_runtime_dev_runbook.md`
- `contracts/deployment/deployment_runbook.md`

Current commands:

- API: `cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- Frontend: `cd frontend && npm run dev`
- PostgreSQL target check: `database/postgres/scripts/check_db_target.sh`
- Worker: `python worker/worker_runtime/cli.py config-check --role all`

What this doc does not cover:

- Detailed API contracts
- Feature-by-feature UI behavior
- Deployment sequencing beyond runtime entrypoints
- Worker operational procedures beyond the CLI entrypoint

Read-first links:

- `docs/current/runtime/api.md`
- `docs/current/runtime/frontend.md`
- `docs/current/runtime/postgres.md`
- `docs/current/runtime/worker.md`
