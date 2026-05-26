---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# Worker Runtime

Purpose: current worker orchestration and runtime operations summary.

Current status:

- Worker runtime exists for `dispatcher`, `capture`, and `grading`.
- Runtime execution uses the app role; seed and cleanup use the maintenance role.

Current source paths:

- `contracts/worker/worker_runtime_dev_runbook.md`
- `contracts/deployment/deployment_runbook.md`
- `database/postgres/README.md`

Current commands:

- Config check: `python worker/worker_runtime/cli.py config-check --role all`
- Dispatcher: `python worker/worker_runtime/cli.py run-dispatcher --once ...`
- Capture: `python worker/worker_runtime/cli.py run-capture --once ...`
- Grading: `python worker/worker_runtime/cli.py run-grading --once`

What this doc does not cover:

- Frontend behavior
- API contract details
- Deployment topology beyond worker CLI entrypoints

Read-first links:

- `docs/current/deployment/README.md`
- `docs/current/runtime/postgres.md`
