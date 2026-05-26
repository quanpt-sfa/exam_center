---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# Frontend

Purpose:
- Hold the staged current React/Vite frontend under `frontend/**`.

Copied source root:
- `frontend/**`

Current staging status:
- Frontend runtime is staged for review from the approved current source root.

Copied structure summary:
- `src/`
- `tests/`
- `e2e/`
- `scripts/`
- `package.json`
- `vite.config.ts`
- `tsconfig*.json`
- `.env.example`
- `.env.lan.example`

Read-first files:
- `frontend/AGENTS.md`
- `frontend/src/main.tsx`
- `frontend/src/app/router.tsx`

Validation/checker references:
- `python tools/docs/check_project_readiness.py`
- `python tools/docs/check_legacy_boundaries.py`

Known limitation:
- Some copied commands may still assume repo-root context until `apps-next` is promoted.
