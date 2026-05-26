# ACF-2 Submission Processing Status Contract

Status:
- Formal API contract for frontend polling/result UI integration.

Prerequisite:
- `contracts/api/submission_processing_status_contract_freeze_plan.md` exists.

Scope:
- Documentation-only contract.
- No runtime behavior change.
- No frontend implementation.

## 1. Endpoint

### Method
- `GET`

### Path
- `/api/v1/submissions/{exam_submission_id}/processing-status`

### Auth requirement
- Authenticated user is required via submission access dependency.
- Allowed roles follow backend policy in `require_submission_access`:
  - `ADMIN`
  - `ACADEMIC_OFFICER`
  - `INSTRUCTOR`
  - `PROCTOR`
  - `STUDENT`

### Path params
- `exam_submission_id`
  - type: integer
  - constraints: `> 0`

### Response content type
- `application/json`
- success envelope shape: `{ "data": <ProcessingStatusPayload>, ... }`
- error envelope shape: `{ "error": { "code": string, "message": string, "details": object } }`

## 2. Permission Behavior

- Student can read own submission processing status.
- Student cannot read another student's submission status.
- Elevated roles above are accepted by route-level policy and then processed by existing access service policy.

### 403 behavior
- Returned when access is denied.
- Primary code observed: `permission_denied`.
- Frontend action: stop polling for this submission and show access denied state.

### 404 behavior
- Returned when submission is not found for access check.
- Code: `submission_not_found`.
- Frontend action: stop polling and show not-found state.

### 503 database unavailable behavior
- Returned on DB connectivity failures mapped by route (`OperationalError`/`InterfaceError`).
- Code: `database_unavailable`.
- Message/details are sanitized and must not leak secrets.
- Frontend action: retry with backoff.

## 3. Overall Status Enum

Note on `SEALED`:
- `SEALED` is not currently emitted by `ProcessingOverallStatus` in runtime model.
- In current implementation, the "sealed checkpoint" is represented by downstream statuses (`WAITING_CAPTURE` or `WAITING_GRADING`) once sealed answers exist.
- Frontend must not rely on receiving `SEALED` from current backend response.

| Status | Meaning | Terminal | Frontend action | Polling | Score may be available | `failure_reason` may be available |
|---|---|---|---|---|---|---|
| `NOT_FOUND` | Submission snapshot missing in classifier. Route maps to HTTP 404 instead of returning this in success payload. | Terminal | Show not found. | Stop | No | Internally yes (`SUBMISSION_NOT_FOUND`), but normal API response is 404 error envelope. |
| `DRAFT_OR_UNSEALED` | Submission is not sealed yet or has no sealed answers. | Non-terminal | Show "not submitted/sealed" state. | Continue only if user can still submit; otherwise UI may pause until seal action. | No | No |
| `SEALED` | Conceptual/legacy checkpoint only; currently represented by `WAITING_CAPTURE` or `WAITING_GRADING` in API responses. | Non-terminal (conceptual) | Treat as pre-processing queued state if ever introduced. | Continue | Usually no | No |
| `WAITING_CAPTURE` | Capture is required but capture evidence is not complete yet. | Non-terminal | Show waiting-for-capture state. | Continue | No | No |
| `CAPTURING` | Capture job is actively running. | Non-terminal | Show capture in progress. | Continue | No | No |
| `CAPTURE_FAILED` | Required capture failed. | Terminal | Show capture failure and retry option if allowed by product flow. | Stop automatic polling; allow manual retry trigger flow. | Normally no | Yes (capture error code or fallback `CAPTURE_FAILED`) |
| `WAITING_GRADING` | Capture satisfied/not required; grading has not started. | Non-terminal | Show queued-for-grading state. | Continue | No | No |
| `GRADING` | Grading is running or active tasks exist. | Non-terminal | Show grading in progress. | Continue | Usually no | No |
| `GRADING_FAILED` | Grading failed/cancelled/partially failed, or failed tasks detected. | Terminal | Show grading failure and retry guidance if supported. | Stop automatic polling; allow manual retry trigger flow. | Usually no | Yes (`GRADING_FAILED`) |
| `COMPLETED` | Submission score exists and task/result consistency is resolved. | Terminal | Show final result/score UI. | Stop | Yes | No |
| `NEEDS_REVIEW` | Ambiguous/manual-review-required state (for example score exists while tasks unresolved). | Terminal | Show manual review pending/result not final state. | Stop | Yes (may exist) | Usually no |

## 4. Response Schema

Model source:
- `ProcessingStatusPayload` and nested models in `backend/app/modules/submission/processing_status_models.py`.

Conventions:
- "Required" means field key is expected in successful payload.
- "Nullable" means value may be `null`.
- Nested objects are always present in successful payload.

### 4.1 Top-level fields

| Field | Type | Required/Nullable | Frontend interpretation | Redaction note |
|---|---|---|---|---|
| `exam_submission_id` | integer | Required, non-null | Submission identity for polling correlation. | None |
| `overall_status` | string enum | Required, non-null | Primary state machine driver for UI flow. | Must remain status-only, no raw internals. |
| `is_terminal` | boolean | Required, non-null | Whether backend state is terminal for polling. | None |
| `can_retry` | boolean | Required, non-null | Whether backend classifies state as retryable (typically failure states). | None |
| `pending_reason` | string | Nullable | Optional machine-readable pending reason for non-terminal or review states. | Must not contain secrets/raw payload. |
| `failure_reason` | string | Nullable | Optional machine-readable failure reason for failed states. | Must be sanitized code-like value, not raw stack/SQL. |
| `seal` | object | Required, non-null | Seal checkpoint summary. | No sealed raw answer text is exposed. |
| `capture` | object | Required, non-null | Capture pipeline summary. | `latest_error_message_sanitized` must be sanitized. |
| `grading` | object | Required, non-null | Grading pipeline summary. | No raw answer/capture content. |
| `tasks` | object | Required, non-null | Task counters and grouping stats. | Aggregate counts only. |
| `results` | object | Required, non-null | Result artifacts counters. | Aggregate counts only. |
| `score` | object | Required, non-null | Score summary for result UI. | Numeric/status summary only. |
| `timestamps` | object | Required, non-null | Created/updated/latest activity timeline. | No raw trace content. |

### 4.2 `seal` fields

| Field | Type | Required/Nullable | Frontend interpretation | Redaction note |
|---|---|---|---|---|
| `seal.submission_seal_id` | integer | Nullable | Presence indicates seal row exists. | Identifier only. |
| `seal.seal_status` | string | Nullable | Seal row status label from backend. | No payload text. |
| `seal.sealed_at` | ISO-8601 datetime string | Nullable | Seal completion timestamp. | None |
| `seal.sealed_answer_count` | integer | Required, non-null | Number of sealed answers. | Count only, no answer body. |
| `seal.has_sealed_answer` | boolean | Required, non-null | Whether sealed answers exist. | None |

### 4.3 `capture` fields

| Field | Type | Required/Nullable | Frontend interpretation | Redaction note |
|---|---|---|---|---|
| `capture.required` | boolean | Required, non-null | Whether capture stage is required. | None |
| `capture.status` | string | Nullable | Current capture job status if job exists. | No raw SQL/data rows. |
| `capture.capture_job_id` | integer | Nullable | Latest capture job identity. | Identifier only. |
| `capture.capture_profile_id` | integer | Nullable | Capture profile reference. | Identifier only. |
| `capture.artifact_count` | integer | Required, non-null | Number of capture artifacts. | Count only. |
| `capture.dataset_count` | integer | Required, non-null | Number of capture datasets. | Count only. |
| `capture.latest_event_type` | string | Nullable | Latest capture event label. | No row payload. |
| `capture.latest_error_code` | string | Nullable | Capture error code. | Code only. |
| `capture.latest_error_message_sanitized` | string | Nullable | Sanitized capture error summary. | Must redact DSN/password/token/trace/SQL internals. |

### 4.4 `grading` fields

| Field | Type | Required/Nullable | Frontend interpretation | Redaction note |
|---|---|---|---|---|
| `grading.grading_job_id` | integer | Nullable | Latest grading job identity. | Identifier only. |
| `grading.grading_job_status` | string | Nullable | Grading job status. | Status only. |
| `grading.grading_run_id` | integer | Nullable | Latest run identity for job. | Identifier only. |
| `grading.grading_run_status` | string | Nullable | Latest run status. | Status only. |
| `grading.worker_id` | string | Nullable | Worker claim marker (operational). | No secrets expected. |
| `grading.claimed_at` | ISO-8601 datetime string | Nullable | Run start time. | None |
| `grading.finished_at` | ISO-8601 datetime string | Nullable | Run finish time. | None |
| `grading.latest_event_type` | string | Nullable | Latest grading event label. | No stack/internal SQL text. |

### 4.5 `tasks` fields

| Field | Type | Required/Nullable | Frontend interpretation | Redaction note |
|---|---|---|---|---|
| `tasks.total` | integer | Required, non-null | Total task count. | Aggregate only. |
| `tasks.queued` | integer | Required, non-null | Queued task count. | Aggregate only. |
| `tasks.running` | integer | Required, non-null | Running task count. | Aggregate only. |
| `tasks.waiting_capture` | integer | Required, non-null | Waiting-capture task count. | Aggregate only. |
| `tasks.completed` | integer | Required, non-null | Completed task count. | Aggregate only. |
| `tasks.failed` | integer | Required, non-null | Failed task count. | Aggregate only. |
| `tasks.needs_review` | integer | Required, non-null | Needs-review task count. | Aggregate only. |
| `tasks.by_input_source` | object<string, integer> | Required, non-null | Grouped counts by input source. | Aggregate only. |
| `tasks.by_answer_language` | object<string, integer> | Required, non-null | Grouped counts by language. | Aggregate only. |

### 4.6 `results` fields

| Field | Type | Required/Nullable | Frontend interpretation | Redaction note |
|---|---|---|---|---|
| `results.actual_result_count` | integer | Required, non-null | Count of actual results. | Aggregate only. |
| `results.comparison_count` | integer | Required, non-null | Count of expected-vs-actual comparisons. | Aggregate only. |
| `results.question_score_count` | integer | Required, non-null | Count of question score rows. | Aggregate only. |

### 4.7 `score` fields

| Field | Type | Required/Nullable | Frontend interpretation | Redaction note |
|---|---|---|---|---|
| `score.submission_score_id` | integer | Nullable | Score row presence/current version marker. | Identifier only. |
| `score.total_score` | number | Nullable | Final/working total score value. | Numeric summary only. |
| `score.max_score` | number | Nullable | Maximum score reference. | Numeric summary only. |
| `score.score_status` | string | Nullable | Score status label for UI badge/state. | Status only. |
| `score.finalized_at` | ISO-8601 datetime string | Nullable | Finalization timestamp. | None |

### 4.8 `timestamps` fields

| Field | Type | Required/Nullable | Frontend interpretation | Redaction note |
|---|---|---|---|---|
| `timestamps.created_at` | ISO-8601 datetime string | Nullable | Submission creation time. | None |
| `timestamps.updated_at` | ISO-8601 datetime string | Nullable | Submission row update time. | None |
| `timestamps.latest_activity_at` | ISO-8601 datetime string | Nullable | Most recent pipeline activity time. | None |

## 5. Redaction Contract

The processing-status API must not return any of the following:
- `submission.answer_state`
- sealed answer text
- raw SQL/code answer bodies
- raw capture dataset rows
- DSN values
- password or secret values
- stack trace text
- raw SQL statements from internal errors

Existing guard coverage sources:
- `backend/tests/test_processing_status_static_guards.py`
- `backend/tests/test_processing_status_api_unit.py`
- `backend/tests/test_processing_status_service_unit.py`

## 6. Polling Recommendation

Suggested frontend polling policy:
- Poll while `is_terminal == false`.
- Stop polling when `is_terminal == true`.
- On HTTP `503`, retry with exponential backoff (for example 2s -> 4s -> 8s, capped).
- Do not repeatedly poll on HTTP `403` or `404`; surface stable error state.
- Recommended default polling interval for normal non-terminal states: `3 seconds`.

## 7. Versioning and Compatibility

Compatibility rules for this contract:
- Additive fields are allowed if they do not alter meaning of existing fields.
- Removing or renaming an existing field requires a contract version change and migration note.
- Adding enum values is allowed only with frontend fallback behavior (unknown status handler).
- Removing enum values requires migration note and coordinated frontend/backend release.

Frontend fallback requirement:
- If unknown `overall_status` is encountered, frontend should:
  - keep rendering a generic in-progress/review-safe state,
  - continue polling unless `is_terminal == true`,
  - avoid assuming score completeness unless score fields are present and terminal semantics are met.

### OpenAPI Snapshot Update Policy

Focused snapshot file:
- `contracts/api/openapi_submission_processing_status_snapshot.json`

Update rules:
- Update this snapshot only when a deliberate contract change is approved for the processing-status endpoint.
- Keep snapshot scope limited to this single route and avoid full-document OpenAPI snapshots.
- Do not include volatile metadata (for example generated IDs unrelated to contract semantics).
- Any snapshot update must be accompanied by corresponding updates in:
  - `contracts/api/submission_processing_status_contract.md`
  - `contracts/api/submission_processing_status_state_machine.md`
  - `contracts/api/submission_processing_status_examples.md`
- Snapshot updates must pass contract regression tests and must not weaken redaction/access requirements.

## 8. Examples

Compact success example (`GRADING`):

```json
{
  "data": {
    "exam_submission_id": 123,
    "overall_status": "GRADING",
    "is_terminal": false,
    "can_retry": false,
    "pending_reason": "GRADING_IN_PROGRESS",
    "failure_reason": null,
    "seal": {
      "submission_seal_id": 9001,
      "seal_status": "SEALED",
      "sealed_at": "2026-05-13T08:00:00Z",
      "sealed_answer_count": 3,
      "has_sealed_answer": true
    },
    "capture": {
      "required": false,
      "status": null,
      "capture_job_id": null,
      "capture_profile_id": null,
      "artifact_count": 0,
      "dataset_count": 0,
      "latest_event_type": null,
      "latest_error_code": null,
      "latest_error_message_sanitized": null
    },
    "grading": {
      "grading_job_id": 7001,
      "grading_job_status": "RUNNING",
      "grading_run_id": 7011,
      "grading_run_status": "RUNNING",
      "worker_id": "grading-worker-1",
      "claimed_at": "2026-05-13T08:01:00Z",
      "finished_at": null,
      "latest_event_type": "RUN_STARTED"
    },
    "tasks": {
      "total": 3,
      "queued": 1,
      "running": 2,
      "waiting_capture": 0,
      "completed": 0,
      "failed": 0,
      "needs_review": 0,
      "by_input_source": {"SEALED_TEXT_ANSWER": 3},
      "by_answer_language": {"SQL": 3}
    },
    "results": {
      "actual_result_count": 0,
      "comparison_count": 0,
      "question_score_count": 0
    },
    "score": {
      "submission_score_id": null,
      "total_score": null,
      "max_score": null,
      "score_status": null,
      "finalized_at": null
    },
    "timestamps": {
      "created_at": "2026-05-13T07:58:00Z",
      "updated_at": "2026-05-13T08:02:00Z",
      "latest_activity_at": "2026-05-13T08:02:00Z"
    }
  }
}
```

Compact error example (`404`):

```json
{
  "error": {
    "code": "submission_not_found",
    "message": "Submission not found",
    "details": {
      "exam_submission_id": 999999
    }
  }
}
```

Verification references used for this contract:
- Route implementation: `backend/app/api/v1/submission.py`
- Use-case access enforcement: `backend/app/modules/submission/use_cases/submission_runtime.py`
- Response model/service: `backend/app/modules/submission/processing_status_models.py`, `backend/app/modules/submission/services/submission_processing_status_service.py`
- API unit tests: `backend/tests/test_processing_status_api_unit.py`
- Status service unit tests: `backend/tests/test_processing_status_service_unit.py`
- Static guards: `backend/tests/test_processing_status_static_guards.py`
