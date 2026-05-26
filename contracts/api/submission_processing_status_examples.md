# ACF-4 Processing Status Examples and Golden Fixtures

Purpose:
- Provide stable, synthetic response examples for frontend integration and contract-test reuse.

Golden fixture directory:
- backend/tests/fixtures/processing_status

## 1. WAITING_GRADING

Fixture:
- backend/tests/fixtures/processing_status/waiting_grading.json

```json
{
  "exam_submission_id": 12001,
  "overall_status": "WAITING_GRADING",
  "is_terminal": false,
  "can_retry": false,
  "pending_reason": "GRADING_NOT_STARTED",
  "failure_reason": null,
  "seal": {
    "submission_seal_id": 91001,
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
    "grading_job_id": null,
    "grading_job_status": null,
    "grading_run_id": null,
    "grading_run_status": null,
    "worker_id": null,
    "claimed_at": null,
    "finished_at": null,
    "latest_event_type": null
  },
  "tasks": {
    "total": 3,
    "queued": 0,
    "running": 0,
    "waiting_capture": 0,
    "completed": 0,
    "failed": 0,
    "needs_review": 0,
    "by_input_source": {
      "SEALED_TEXT_ANSWER": 3
    },
    "by_answer_language": {
      "SQL": 3
    }
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
    "created_at": "2026-05-13T07:55:00Z",
    "updated_at": "2026-05-13T08:00:00Z",
    "latest_activity_at": "2026-05-13T08:00:00Z"
  }
}
```

## 2. WAITING_CAPTURE

Fixture:
- backend/tests/fixtures/processing_status/waiting_capture.json

```json
{
  "exam_submission_id": 12002,
  "overall_status": "WAITING_CAPTURE",
  "is_terminal": false,
  "can_retry": false,
  "pending_reason": "CAPTURE_NOT_COMPLETED",
  "failure_reason": null,
  "seal": {
    "submission_seal_id": 91002,
    "seal_status": "SEALED",
    "sealed_at": "2026-05-13T08:01:00Z",
    "sealed_answer_count": 2,
    "has_sealed_answer": true
  },
  "capture": {
    "required": true,
    "status": "QUEUED",
    "capture_job_id": 93002,
    "capture_profile_id": 4402,
    "artifact_count": 0,
    "dataset_count": 0,
    "latest_event_type": "CAPTURE_REQUESTED",
    "latest_error_code": null,
    "latest_error_message_sanitized": null
  },
  "grading": {
    "grading_job_id": null,
    "grading_job_status": null,
    "grading_run_id": null,
    "grading_run_status": null,
    "worker_id": null,
    "claimed_at": null,
    "finished_at": null,
    "latest_event_type": null
  },
  "tasks": {
    "total": 2,
    "queued": 0,
    "running": 0,
    "waiting_capture": 2,
    "completed": 0,
    "failed": 0,
    "needs_review": 0,
    "by_input_source": {
      "CAPTURE_DATASET": 2
    },
    "by_answer_language": {
      "SQL": 2
    }
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
    "created_at": "2026-05-13T07:56:00Z",
    "updated_at": "2026-05-13T08:02:00Z",
    "latest_activity_at": "2026-05-13T08:02:00Z"
  }
}
```

## 3. CAPTURING

Fixture:
- backend/tests/fixtures/processing_status/capturing.json

```json
{
  "exam_submission_id": 12003,
  "overall_status": "CAPTURING",
  "is_terminal": false,
  "can_retry": false,
  "pending_reason": "CAPTURE_RUNNING",
  "failure_reason": null,
  "seal": {
    "submission_seal_id": 91003,
    "seal_status": "SEALED",
    "sealed_at": "2026-05-13T08:03:00Z",
    "sealed_answer_count": 4,
    "has_sealed_answer": true
  },
  "capture": {
    "required": true,
    "status": "RUNNING",
    "capture_job_id": 93003,
    "capture_profile_id": 4403,
    "artifact_count": 1,
    "dataset_count": 0,
    "latest_event_type": "CAPTURE_STARTED",
    "latest_error_code": null,
    "latest_error_message_sanitized": null
  },
  "grading": {
    "grading_job_id": null,
    "grading_job_status": null,
    "grading_run_id": null,
    "grading_run_status": null,
    "worker_id": null,
    "claimed_at": null,
    "finished_at": null,
    "latest_event_type": null
  },
  "tasks": {
    "total": 4,
    "queued": 0,
    "running": 0,
    "waiting_capture": 4,
    "completed": 0,
    "failed": 0,
    "needs_review": 0,
    "by_input_source": {
      "CAPTURE_DATASET": 4
    },
    "by_answer_language": {
      "SQL": 4
    }
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
    "created_at": "2026-05-13T07:57:00Z",
    "updated_at": "2026-05-13T08:04:00Z",
    "latest_activity_at": "2026-05-13T08:04:00Z"
  }
}
```

## 4. GRADING

Fixture:
- backend/tests/fixtures/processing_status/grading.json

```json
{
  "exam_submission_id": 12004,
  "overall_status": "GRADING",
  "is_terminal": false,
  "can_retry": false,
  "pending_reason": "GRADING_IN_PROGRESS",
  "failure_reason": null,
  "seal": {
    "submission_seal_id": 91004,
    "seal_status": "SEALED",
    "sealed_at": "2026-05-13T08:05:00Z",
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
    "grading_job_id": 94004,
    "grading_job_status": "RUNNING",
    "grading_run_id": 95004,
    "grading_run_status": "RUNNING",
    "worker_id": "grading-worker-a",
    "claimed_at": "2026-05-13T08:05:30Z",
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
    "by_input_source": {
      "SEALED_TEXT_ANSWER": 3
    },
    "by_answer_language": {
      "SQL": 3
    }
  },
  "results": {
    "actual_result_count": 1,
    "comparison_count": 1,
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
    "created_at": "2026-05-13T08:00:00Z",
    "updated_at": "2026-05-13T08:06:00Z",
    "latest_activity_at": "2026-05-13T08:06:00Z"
  }
}
```

## 5. COMPLETED (with score)

Fixture:
- backend/tests/fixtures/processing_status/completed.json

```json
{
  "exam_submission_id": 12005,
  "overall_status": "COMPLETED",
  "is_terminal": true,
  "can_retry": false,
  "pending_reason": null,
  "failure_reason": null,
  "seal": {
    "submission_seal_id": 91005,
    "seal_status": "SEALED",
    "sealed_at": "2026-05-13T08:07:00Z",
    "sealed_answer_count": 2,
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
    "grading_job_id": 94005,
    "grading_job_status": "COMPLETED",
    "grading_run_id": 95005,
    "grading_run_status": "COMPLETED",
    "worker_id": "grading-worker-b",
    "claimed_at": "2026-05-13T08:07:20Z",
    "finished_at": "2026-05-13T08:08:30Z",
    "latest_event_type": "RUN_COMPLETED"
  },
  "tasks": {
    "total": 2,
    "queued": 0,
    "running": 0,
    "waiting_capture": 0,
    "completed": 2,
    "failed": 0,
    "needs_review": 0,
    "by_input_source": {
      "SEALED_TEXT_ANSWER": 2
    },
    "by_answer_language": {
      "SQL": 2
    }
  },
  "results": {
    "actual_result_count": 2,
    "comparison_count": 2,
    "question_score_count": 2
  },
  "score": {
    "submission_score_id": 97005,
    "total_score": 8.5,
    "max_score": 10.0,
    "score_status": "FINALIZED",
    "finalized_at": "2026-05-13T08:08:35Z"
  },
  "timestamps": {
    "created_at": "2026-05-13T08:01:00Z",
    "updated_at": "2026-05-13T08:08:35Z",
    "latest_activity_at": "2026-05-13T08:08:35Z"
  }
}
```

## 6. CAPTURE_FAILED (sanitized failure)

Fixture:
- backend/tests/fixtures/processing_status/capture_failed.json

```json
{
  "exam_submission_id": 12006,
  "overall_status": "CAPTURE_FAILED",
  "is_terminal": true,
  "can_retry": true,
  "pending_reason": null,
  "failure_reason": "CAPTURE_TIMEOUT",
  "seal": {
    "submission_seal_id": 91006,
    "seal_status": "SEALED",
    "sealed_at": "2026-05-13T08:09:00Z",
    "sealed_answer_count": 5,
    "has_sealed_answer": true
  },
  "capture": {
    "required": true,
    "status": "FAILED",
    "capture_job_id": 93006,
    "capture_profile_id": 4406,
    "artifact_count": 0,
    "dataset_count": 0,
    "latest_event_type": "CAPTURE_FAILED",
    "latest_error_code": "CAPTURE_TIMEOUT",
    "latest_error_message_sanitized": "Capture request timed out while collecting source snapshot."
  },
  "grading": {
    "grading_job_id": null,
    "grading_job_status": null,
    "grading_run_id": null,
    "grading_run_status": null,
    "worker_id": null,
    "claimed_at": null,
    "finished_at": null,
    "latest_event_type": null
  },
  "tasks": {
    "total": 5,
    "queued": 0,
    "running": 0,
    "waiting_capture": 5,
    "completed": 0,
    "failed": 0,
    "needs_review": 0,
    "by_input_source": {
      "CAPTURE_DATASET": 5
    },
    "by_answer_language": {
      "SQL": 5
    }
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
    "created_at": "2026-05-13T08:02:00Z",
    "updated_at": "2026-05-13T08:10:00Z",
    "latest_activity_at": "2026-05-13T08:10:00Z"
  }
}
```

## 7. GRADING_FAILED (sanitized failure)

Fixture:
- backend/tests/fixtures/processing_status/grading_failed.json

```json
{
  "exam_submission_id": 12007,
  "overall_status": "GRADING_FAILED",
  "is_terminal": true,
  "can_retry": true,
  "pending_reason": null,
  "failure_reason": "GRADING_FAILED",
  "seal": {
    "submission_seal_id": 91007,
    "seal_status": "SEALED",
    "sealed_at": "2026-05-13T08:11:00Z",
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
    "grading_job_id": 94007,
    "grading_job_status": "FAILED",
    "grading_run_id": 95007,
    "grading_run_status": "FAILED",
    "worker_id": "grading-worker-c",
    "claimed_at": "2026-05-13T08:11:20Z",
    "finished_at": "2026-05-13T08:12:15Z",
    "latest_event_type": "RUN_FAILED"
  },
  "tasks": {
    "total": 3,
    "queued": 0,
    "running": 0,
    "waiting_capture": 0,
    "completed": 1,
    "failed": 2,
    "needs_review": 0,
    "by_input_source": {
      "SEALED_TEXT_ANSWER": 3
    },
    "by_answer_language": {
      "SQL": 3
    }
  },
  "results": {
    "actual_result_count": 1,
    "comparison_count": 1,
    "question_score_count": 1
  },
  "score": {
    "submission_score_id": null,
    "total_score": null,
    "max_score": null,
    "score_status": null,
    "finalized_at": null
  },
  "timestamps": {
    "created_at": "2026-05-13T08:03:00Z",
    "updated_at": "2026-05-13T08:12:15Z",
    "latest_activity_at": "2026-05-13T08:12:15Z"
  }
}
```

## 8. NEEDS_REVIEW

Fixture:
- backend/tests/fixtures/processing_status/needs_review.json

```json
{
  "exam_submission_id": 12008,
  "overall_status": "NEEDS_REVIEW",
  "is_terminal": true,
  "can_retry": false,
  "pending_reason": "MANUAL_REVIEW_REQUIRED",
  "failure_reason": null,
  "seal": {
    "submission_seal_id": 91008,
    "seal_status": "SEALED",
    "sealed_at": "2026-05-13T08:13:00Z",
    "sealed_answer_count": 4,
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
    "grading_job_id": 94008,
    "grading_job_status": "COMPLETED",
    "grading_run_id": 95008,
    "grading_run_status": "COMPLETED",
    "worker_id": "grading-worker-d",
    "claimed_at": "2026-05-13T08:13:20Z",
    "finished_at": "2026-05-13T08:14:10Z",
    "latest_event_type": "RUN_COMPLETED"
  },
  "tasks": {
    "total": 4,
    "queued": 0,
    "running": 0,
    "waiting_capture": 0,
    "completed": 3,
    "failed": 0,
    "needs_review": 1,
    "by_input_source": {
      "SEALED_TEXT_ANSWER": 4
    },
    "by_answer_language": {
      "SQL": 4
    }
  },
  "results": {
    "actual_result_count": 4,
    "comparison_count": 4,
    "question_score_count": 3
  },
  "score": {
    "submission_score_id": 97008,
    "total_score": 6.0,
    "max_score": 10.0,
    "score_status": "NEEDS_REVIEW",
    "finalized_at": null
  },
  "timestamps": {
    "created_at": "2026-05-13T08:04:00Z",
    "updated_at": "2026-05-13T08:14:10Z",
    "latest_activity_at": "2026-05-13T08:14:10Z"
  }
}
```

## 9. 403 Forbidden Error Shape

```json
{
  "error": {
    "code": "permission_denied",
    "message": "Insufficient permissions",
    "details": {
      "exam_submission_id": 12009
    }
  }
}
```

## 10. 404 Not Found Error Shape

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

## 11. 503 Database Unavailable Error Shape

```json
{
  "error": {
    "code": "database_unavailable",
    "message": "Database temporarily unavailable",
    "details": {
      "exam_submission_id": 12010
    }
  }
}
```

## Schema and Safety Notes

- All examples are synthetic and non-production.
- Nullable fields are explicit with `null` values.
- Examples align with `ProcessingStatusPayload` top-level and nested schema.
- Sensitive/raw content is intentionally excluded from all examples.
