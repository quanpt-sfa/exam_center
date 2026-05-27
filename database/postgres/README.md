# PostgreSQL Runtime

Purpose:
- Hold the active PostgreSQL schema, scripts, and DB checks under `database/postgres/**`.

Structure summary:
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
- `python database/postgres/scripts/check_test_db_target.py`
