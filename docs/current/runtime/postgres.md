---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# PostgreSQL Runtime

Purpose: current PostgreSQL database and migration runtime summary.

Current status:

- PostgreSQL is the current database runtime.
- Local and LAN DB targeting is driven from root `.env.lan`.
- Migrations and smoke tests are additive and phase-driven.

Current source paths:

- `database/postgres/README.md`
- `contracts/deployment/deployment_runbook.md`

Current commands:

- DB target check: `database/postgres/scripts/check_db_target.sh`
- Create DB: `database/postgres/scripts/create_database.sh`
- Run migrations: `database/postgres/scripts/run_phase1_migrations.sh`
- Run smoke tests: `database/postgres/scripts/run_smoke_tests.sh`

What this doc does not cover:

- API endpoint behavior
- Frontend behavior
- Worker task semantics beyond database prerequisites

Read-first links:

- `docs/current/runtime/api.md`
- `docs/current/deployment/README.md`
