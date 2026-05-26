---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# API Contracts

Purpose: route API work to the narrowest current contract and implementation paths.

Current status:

- API contracts live in `contracts/api/**`.
- Backend code lives under `backend/**`.

Current source paths:

- `contracts/api/auth_api.md`
- `contracts/api/assessment_api.md`
- `contracts/api/delivery_submission_api.md`
- `contracts/api/capture_api.md`
- `contracts/api/grading_api.md`
- `contracts/api/import_api.md`
- `contracts/api/ops_api.md`
- `contracts/api/submission_processing_status_contract.md`

Current commands:

- API tests: `cd backend && python -m pytest -q`
- API start: `cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`

| Domain | Source contract docs | Implementation paths if known | Status | Read first | Read if needed |
|---|---|---|---|---|---|
| `auth` | `contracts/api/auth_api.md` | `backend/app/api/v1/auth.py`<br>`backend/app/modules/auth/` | `current` | `contracts/api/auth_api.md` | `docs/current/runtime/api.md` |
| `assessment` | `contracts/api/assessment_api.md` | `backend/app/api/v1/assessment.py`<br>`backend/app/modules/assessment/` | `current` | `contracts/api/assessment_api.md` | `docs/current/runtime/api.md` |
| `delivery/submission` | `contracts/api/delivery_submission_api.md`<br>`contracts/api/file_answer_submission_api.md` | `backend/app/api/v1/delivery.py`<br>`backend/app/api/v1/submission.py`<br>`backend/app/modules/delivery/`<br>`backend/app/modules/submission/` | `current` | `contracts/api/delivery_submission_api.md` | `contracts/api/file_answer_submission_api.md` |
| `capture` | `contracts/api/capture_api.md` | `backend/app/api/v1/capture.py`<br>`backend/app/modules/capture/` | `current` | `contracts/api/capture_api.md` | `docs/current/runtime/worker.md` |
| `grading` | `contracts/api/grading_api.md` | `backend/app/api/v1/grading.py`<br>`backend/app/modules/grading/` | `current` | `contracts/api/grading_api.md` | `docs/current/runtime/worker.md` |
| `import` | `contracts/api/import_api.md` | `backend/app/api/v1/imports.py`<br>`backend/app/modules/importing/` | `current` | `contracts/api/import_api.md` | `docs/current/runtime/api.md` |
| `ops` | `contracts/api/ops_api.md` | `backend/app/api/v1/ops.py`<br>`backend/app/api/v1/system_settings.py`<br>`backend/app/modules/ops/` | `current` | `contracts/api/ops_api.md` | `docs/current/deployment/README.md` |
| `submission processing status` | `contracts/api/submission_processing_status_contract.md` | `backend/app/api/v1/submission.py`<br>`backend/app/modules/submission/services/submission_processing_status_service.py` | `current` | `contracts/api/submission_processing_status_contract.md` | `contracts/api/submission_processing_status_examples.md` |

What this doc does not cover:

- Runtime setup beyond the backend entrypoint
- Frontend UX behavior
- Database migration sequencing

Read-first links:

- `docs/current/runtime/api.md`
- `docs/current/runtime/postgres.md`
