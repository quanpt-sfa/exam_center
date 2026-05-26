# Grading API Skeleton

This document defines the grading API skeleton for Phase 5A orchestration.

## Scope

Implemented in FastAPI module routes and service/repository foundation only.

- Included:
  - Queue grading jobs from sealed submissions
  - Read grading job status and run/task counters
  - Read submission score and question scores
  - Read gradebook list and submission detail summaries
  - Manual review list/read/resolve placeholders
  - Score adjustment with audit events
  - Grading event listing
- Excluded:
  - SQL/Python/R engine execution
  - Worker execution and task processing
  - In-request grading execution
  - Reading `submission.answer_state` for grading
  - Mutation of `submission.sealed_answer`
  - Python sandbox execution or hidden-test execution
  - Automatic Python execution for student code-text submissions

## Base Path

All endpoints are under `/api/v1`.

## Endpoints

### Jobs

- `POST /grading/jobs`
  - Accepts `exam_submission_id` or `submission_seal_id`
  - Requires sealed submission (`submission.submission_seal.seal_status = SEALED`)
  - Requires submission dispatch readiness for `DIRECT_GRADING`
  - Rejects Python-not-ready or capture/manual-only submissions without creating a `grading_job`
  - Creates `grading.grading_job` with `grading_status = QUEUED`
  - Supports idempotency by `(exam_submission_id, idempotency_key)`
  - Writes `grading.grading_event` with `event_type = JOB_QUEUED`
  - Uses one transaction boundary for job create + event logging; failures roll back both

- `GET /grading/jobs/{job_id}`
  - Returns job status from `grading.v_grading_job_status`
  - Returns run summaries from `grading.v_grading_run_status`

- `POST /grading/jobs/{job_id}/retry`
  - Requeues existing job by setting `grading_status = QUEUED`
  - Increments `attempt_count`
  - Writes `grading.grading_event` with `event_type = JOB_QUEUED`

### Scores

- `GET /grading/submissions/{submission_id}/score`
  - Returns current `grading.submission_score` summary if available
  - Returns `{ status: NOT_READY }` when no score exists

- `GET /grading/submissions/{submission_id}/question-scores`
  - Returns list of question-level score summaries

### Gradebook

- `GET /grading/gradebook`
  - Read-only instructor/admin gradebook projection
  - Supports filters:
    - `exam_id`
    - `exam_sitting_id`
    - `exam_sitting_room_id`
    - `class_section_id`
    - `student_query`
    - `grading_status`
    - `submission_status`
    - `needs_review`
    - `limit`
    - `offset`
  - Stable ordering:
    - `sealed_at DESC NULLS LAST`
    - `exam_submission_id DESC`
  - Returns one row per `exam_submission_id`
  - Does not expose raw answers, raw file content, internal file paths, or DSN/configuration internals
  - Derives `grading_status` as:
    - `NEEDS_REVIEW` when open manual review exists, question score requires review, or latest grading job is `NEEDS_REVIEW`
    - `COMPUTED` when current submission score exists
    - `FAILED` when latest grading job is `FAILED` or `PARTIALLY_FAILED`
    - `PENDING` when grading job exists but no current score is available yet
    - `NOT_DISPATCHED` when no grading job exists yet

- `GET /grading/gradebook/submissions/{submission_id}`
  - Read-only instructor/admin detail projection for one submission
  - Returns:
    - `submission`: gradebook row summary
    - `score`: existing submission score shape or `null`
    - `question_scores`: existing question score shape list
    - `manual_reviews`: minimal safe review summaries
    - `jobs`: grading job summaries
    - `events`: safe grading event summaries
  - Does not expose file content, internal storage paths, answer payloads, sandbox DSNs, or database connection details

### Manual Review

- `GET /grading/manual-reviews`
  - Lists review queue rows with optional status filter

- `GET /grading/manual-reviews/{review_id}`
  - Returns one manual review row

- `POST /grading/manual-reviews/{review_id}/resolve`
  - Requires resolution reason
  - Updates review status (`RESOLVED`, `REJECTED`, or `CANCELLED`)
  - Optionally creates score adjustment when `create_score_adjustment = true`
  - Review update, optional score adjustment, and grading event logging run in one transaction boundary

### Manual File Answer Scoring

- `GET /grading/manual-review/file-answers`
  - Lists pending sealed `FILE_REF` answers requiring manual rubric review.

- `GET /grading/manual-review/file-answers/{sealed_answer_id}/content`
  - Streams submitted file through authorized API only.
  - Does not expose internal storage key or filesystem path.

- `POST /grading/manual-review/file-answers/{sealed_answer_id}/score`
  - Validates score range against question `max_score`.
  - Resolves one auditable manual-review row (`grading.manual_review_queue`).
  - Persists official score rows:
    - question-level: `grading.question_score`
    - submission-level current snapshot: `grading.submission_score` (versioned)
  - For rescoring without idempotency key, creates audit evidence via:
    - new `manual_review_queue` row, and
    - `grading.score_adjustment` when score value changes.
  - With same `idempotency_key`, returns prior resolved result (`idempotent=true`).

### Adjustments and Events

- `POST /grading/score-adjustments`
  - Requires reason
  - Creates `grading.score_adjustment`
  - Writes `grading.grading_event` with `event_type = SCORE_ADJUSTED`
  - Adjustment row write and event logging are atomic within one transaction boundary

- `GET /grading/events`
  - Returns event summaries from `grading.v_grading_event_summary`

## Permissions

- Access read endpoints: `ADMIN`, `ACADEMIC_OFFICER`, `INSTRUCTOR`, `PROCTOR`, `STUDENT`
- Gradebook list/detail endpoints: `ADMIN`, `ACADEMIC_OFFICER`, `INSTRUCTOR`
- Manage job/review endpoints: `ADMIN`, `ACADEMIC_OFFICER`, `INSTRUCTOR`, `PROCTOR`
- Score adjustment endpoint: `ADMIN`, `ACADEMIC_OFFICER`, `INSTRUCTOR`

## Gradebook Response Contract

### `GET /grading/gradebook`

```json
{
  "items": [
    {
      "exam_submission_id": 123,
      "student_id": 456,
      "student_code": "SV001",
      "student_full_name": "Nguyen Van A",
      "exam_id": 1,
      "exam_title": "SQL Midterm",
      "exam_sitting_id": 10,
      "exam_sitting_room_id": 98,
      "room_name": "Lab A",
      "submission_status": "SUBMITTED",
      "sealed_at": "2026-05-20T10:00:00+00:00",
      "grading_status": "COMPUTED",
      "total_score": "10.00",
      "max_score": "10.00",
      "percentage": "100.00",
      "needs_review": false,
      "question_score_count": 1,
      "manual_review_count": 0,
      "last_graded_at": "2026-05-20T10:05:00+00:00"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### `GET /grading/gradebook/submissions/{submission_id}`

```json
{
  "submission": {
    "exam_submission_id": 123,
    "student_id": 456,
    "student_code": "SV001",
    "student_full_name": "Nguyen Van A",
    "exam_id": 1,
    "exam_title": "SQL Midterm",
    "exam_sitting_id": 10,
    "exam_sitting_room_id": 98,
    "room_name": "Lab A",
    "submission_status": "SUBMITTED",
    "sealed_at": "2026-05-20T10:00:00+00:00",
    "grading_status": "PENDING",
    "total_score": null,
    "max_score": null,
    "percentage": null,
    "needs_review": false,
    "question_score_count": 0,
    "manual_review_count": 0,
    "last_graded_at": null
  },
  "score": null,
  "question_scores": [],
  "manual_reviews": [],
  "jobs": [],
  "events": []
}
```

## Data Safety Rules

- Grading APIs do not read `submission.answer_state`.
- Grading APIs do not update `submission.sealed_answer`.
- Grading APIs do not execute engines in request path.
- Worker execution remains out of scope and will consume queued jobs later.
- SQL textbox auto-grading remains a separate worker/runtime capability under Phase 2F constraints.
- Python submissions are currently text-only/code-text answers that must stay in manual/deferred review flow.
- Python auto-grading is a future Python auto-grading module and requires a validated sandbox/container runner before any worker integration.
- Automatic Python execution is currently NO-GO.
- Gradebook APIs are MVP role-scoped only; future exam/class ownership scoping remains a follow-up patch.
