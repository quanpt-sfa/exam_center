---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# Frontend

Purpose:
- Hold the active React/Vite frontend under `frontend/**`.

Structure summary:
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
- `cd frontend && npm test -- --run`
