# PostgreSQL Staging Landing

Purpose:
- Hold the staged PostgreSQL runtime copy from `database/postgres/**` inside `database/postgres/**`.

Copied source root:
- `database/postgres/**`

Current staging status:
- PostgreSQL files are staged for review without expanding the allowlist beyond `database/postgres/**`.

Copied structure summary:
- `01_migrations/`
- `02_seeds/`
- `03_views/`
- `04_functions/`
- `05_tests/`
- `scripts/`
- `.env.postgres.example`

Read-first files:
- `database/AGENTS.md`
- `database/postgres/scripts/run_all_migrations.sh`
- `database/postgres/scripts/run_smoke_tests.sh`

Validation/checker references:
- `python tools/docs/check_project_readiness.py`
- `python tools/docs/check_legacy_boundaries.py`

Known limitation:
- Scripts may still assume repo-root context until `apps-next` is promoted.
