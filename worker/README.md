# Worker

Purpose:
- Hold the staged current worker runtime under `worker/**`.

Copied source root:
- `worker/**`

Current staging status:
- Worker runtime is staged for review from the allowed current source root.

Copied structure summary:
- `worker_runtime/`
- `scripts/`
- `tests/`
- `.env.example`
- `.env.lan.example`

Read-first files:
- `worker/AGENTS.md`
- `worker/worker_runtime/cli.py`
- `worker/scripts/run_wro_postgres_integration.py`

Validation/checker references:
- `python tools/docs/check_project_readiness.py`
- `python tools/docs/check_legacy_boundaries.py`

Known limitation:
- Some copied commands may still assume repo-root context until `apps-next` is promoted.
