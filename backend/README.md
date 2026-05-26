# Backend Staging Landing

Purpose:
- Hold the staged backend copy from `backend/**` inside `backend/**`.

Current status:
- Backend files are staged and frozen for provenance and review.

Local read-first files:
- `backend/AGENTS.md`
- `backend/app/main.py`
- `backend/tests/conftest.py`

Validation command references:
- `python tools/docs/check_project_readiness.py`
- `python tools/docs/check_legacy_boundaries.py`

Known limitation:
- Commands may still require repo-root context until the standalone tree is promoted.
