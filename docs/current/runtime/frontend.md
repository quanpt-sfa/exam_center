---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# Frontend Runtime

Purpose: current React/Vite browser runtime summary.

Current status:

- The active frontend is `frontend/**`.
- The browser consumes backend API V1 only.
- UI work stays on the frontend side of the API boundary.

Current source paths:

- `frontend/README.md`
- `backend/README.md`

Current commands:

- Frontend dev server: `cd frontend && npm run dev`
- Frontend tests: `cd frontend && npm run test`
- Frontend build: `cd frontend && npm run build`

What this doc does not cover:

- Database runtime operations
- Worker runtime operations
- Feature-specific UX decisions without feature docs and code

Read-first links:

- `docs/current/features/README.md`
- `docs/current/api/README.md`
- `docs/current/runtime/api.md`
