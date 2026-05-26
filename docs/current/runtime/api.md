---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# API Runtime

Purpose: current FastAPI backend runtime summary.

Current status:

- Backend runtime is FastAPI under `backend/**`.
- API runtime uses PostgreSQL and current API contracts under `contracts/api/**`.
- Deployment and runtime checks live in `contracts/deployment/**`.

Current source paths:

- `backend/README.md`
- `contracts/deployment/deployment_runbook.md`
- `contracts/api/README.md`

Current commands:

- API start: `cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- API tests: `cd backend && python -m pytest -q`
- DB prep: `database/postgres/scripts/check_db_target.sh`

What this doc does not cover:

- Frontend interaction details
- Full migration procedures
- Worker orchestration details

Read-first links:

- `docs/current/api/README.md`
- `docs/current/runtime/postgres.md`
- `docs/current/runtime/worker.md`
