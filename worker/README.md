# Worker

Purpose:
- Hold the active worker runtime under `worker/**`.

Structure summary:
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
- `$env:PYTHONPATH="$PWD\backend;$PWD\worker"; .venv/Scripts/python -m pytest worker/tests -q`
