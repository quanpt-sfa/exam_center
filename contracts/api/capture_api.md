# Capture API Skeleton

This document defines the queue-only capture API skeleton for post-seal capture jobs.

## Scope

Implemented in FastAPI module routes and capture module service/repository foundation.

- Included:
  - Queue capture jobs from sealed submissions
  - Read capture job status via safe status view
  - Read capture dataset metadata list
  - Read capture artifact metadata list
  - Retry/requeue capture jobs
  - Capture job event logging for queue/retry actions
- Excluded:
  - Real MISA/AMIS/database integrations
  - In-request capture execution
  - Capture worker implementation
  - Legacy Flask runtime modifications

## Base Path

All endpoints are under /api/v1.

## Endpoints

- POST /capture/jobs
  - Accepts exam_submission_id or submission_seal_id
  - Requires submission seal status SEALED
  - Resolves capture source from delivery resource binding summary or capture profile summary
  - Creates capture.capture_job with capture_status QUEUED only
  - Logs capture.capture_job_event with CAPTURE_QUEUED
  - Uses one transaction boundary for job row creation and queue-event logging; failures roll back both

- GET /capture/jobs/{job_id}
  - Returns capture job status from capture.v_capture_job_status

- GET /capture/jobs/{job_id}/datasets
  - Returns capture dataset metadata list from capture.capture_dataset
  - Returns empty items list when no datasets exist

- GET /capture/jobs/{job_id}/artifacts
  - Returns capture artifact metadata list from capture.capture_artifact
  - Returns empty items list when no artifacts exist

- POST /capture/jobs/{job_id}/retry
  - Requeues existing job by setting capture_status QUEUED
  - Increments attempt_count on capture.capture_job
  - Clears runtime error fields
  - Logs capture.capture_job_event with CAPTURE_RETRIED

## RBAC

- Capture read access: ADMIN, ACADEMIC_OFFICER, INSTRUCTOR, PROCTOR, STUDENT
- Capture manage access (create/retry): ADMIN, ACADEMIC_OFFICER, INSTRUCTOR, PROCTOR
- Student access is ownership constrained by student_id on the target submission.

## Data Safety

- APIs do not expose delivery exam_session_resource_binding.resource_ref.
- APIs do not expose delivery exam_session_resource_binding.connection_profile_ref.
- Dataset and artifact endpoints return metadata columns only.
- APIs do not execute capture integrations in request path.

## Remaining Worker Work

- Implement worker polling/dispatch for capture.capture_job rows in QUEUED state.
- Implement source-specific adapters (database snapshots, AMIS pulls, file artifact capture).
- Persist capture datasets/artifacts and job lifecycle transitions (RUNNING/COMPLETED/FAILED).
- Add observability and backoff/circuit-breaker policies for integration adapters.
