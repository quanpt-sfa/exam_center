---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# Routing

Purpose: choose the narrowest current-runtime docs before opening code.

When to read: when deciding which current docs to open first.

When not to read: do not use this as a substitute for the source docs or runtime code.

Next files to inspect: `manifest.yaml`, `token-budget.md`.

| Task | Read first | Read if needed | Do not read by default |
|---|---|---|---|
| `quick_edit` | `docs/current/workflows/quick-edit.md`<br>`docs/00-start-here/token-budget.md`<br>`docs/00-start-here/routing.md` | `docs/current/engineering/README.md`<br>`docs/current/features/README.md` | `docs/reports/**`, `reports/**`, `reports/copy-provenance.json` |
| `api_runtime` | `docs/current/runtime/api.md`<br>`docs/current/runtime/postgres.md` | `docs/current/api/README.md`<br>`docs/current/deployment/README.md` | unrelated current domains |
| `api_contract` | `docs/current/api/README.md`<br>`docs/current/runtime/api.md` | `docs/current/runtime/postgres.md`<br>`docs/current/engineering/README.md` | unrelated current domains |
| `postgres_runtime` | `docs/current/runtime/postgres.md`<br>`docs/current/deployment/README.md` | `docs/current/runtime/api.md`<br>`docs/current/engineering/README.md` | unrelated current domains |
| `frontend_runtime` | `docs/current/runtime/frontend.md`<br>`docs/current/features/README.md` | `docs/current/runtime/api.md`<br>`docs/current/engineering/README.md` | unrelated current domains |
| `worker_runtime` | `docs/current/runtime/worker.md`<br>`docs/current/deployment/README.md` | `docs/current/runtime/postgres.md`<br>`docs/current/README.md` | unrelated current domains |
| `deployment` | `docs/current/deployment/README.md`<br>`docs/current/runtime/postgres.md`<br>`docs/current/runtime/api.md` | `docs/current/runtime/worker.md`<br>`docs/current/engineering/README.md` | unrelated current domains |
| `engineering_guardrails` | `docs/current/engineering/README.md`<br>`docs/current/runtime/api.md` | `docs/current/features/README.md`<br>`docs/current/deployment/README.md` | unrelated feature docs |
| `feature_docs` | `docs/current/features/README.md`<br>`docs/current/runtime/frontend.md`<br>`docs/current/runtime/api.md` | `docs/current/engineering/README.md`<br>`docs/current/deployment/README.md` | unrelated current domains |
| `review_needed` | `docs/00-start-here/manifest.yaml`<br>`docs/current/README.md` | `docs/current/engineering/README.md`<br>`docs/current/features/README.md` | unrelated current domains |
| `readiness_audit` | `docs/00-start-here/routing.md`<br>`docs/00-start-here/token-budget.md`<br>`docs/current/engineering/README.md` | `docs/current/features/README.md` | runtime source trees until the audit scope is defined |
