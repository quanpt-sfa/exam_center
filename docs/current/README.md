---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# Current

Purpose: entrypoint for current runtime, contracts, and guardrails.

Current status:

- FastAPI backend under `backend/**`.
- PostgreSQL runtime under `database/postgres/**`.
- React/Vite frontend under `frontend/**`.
- Worker runtime under `worker/**`.

Source-of-truth source paths:

- `docs/current/runtime/README.md`
- `docs/current/api/README.md`
- `docs/current/deployment/README.md`
- `docs/current/engineering/README.md`
- `docs/current/features/README.md`

Required commands or entrypoints if known:

- API: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- Frontend: `cd frontend && npm run dev`
- Worker: `python worker/worker_runtime/cli.py config-check --role all`
- PostgreSQL prep: `database/postgres/scripts/check_db_target.sh`

What not to infer:

- Do not infer that any doc outside `docs/current/**` is the current runtime entrypoint.
- Do not infer that browser code may access the database or worker internals directly.

Contradictions or unknowns:

- None recorded.

Read-next links:

- `docs/current/runtime/README.md`
- `docs/current/api/README.md`
- `docs/current/deployment/README.md`
- `docs/current/engineering/README.md`
- `docs/current/features/README.md`
