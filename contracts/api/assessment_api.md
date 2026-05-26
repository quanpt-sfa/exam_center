# Assessment Authoring API MVP

## Scope

This document defines the MVP authoring API for assessment metadata and authoring primitives only:

- Assessment types
- Exams
- Exam versions
- Question banks
- Questions
- Expected answers (reference solutions)
- Question grading profiles

Out of scope for this MVP:

- Delivery runtime
- Submission pipeline
- Worker orchestration
- Frontend integrations

## Base Path

`/api/v1`

## Authentication and RBAC

All endpoints require authenticated user context.

- Read endpoints: roles `ADMIN`, `ACADEMIC_OFFICER`, `INSTRUCTOR`
- Write endpoints: roles `ADMIN`, `ACADEMIC_OFFICER`, `INSTRUCTOR`
- Student role (`STUDENT`) cannot author or mutate content.

Permission failures return:

- HTTP `403`
- Error code: `permission_denied`

## Endpoints

### Assessment Types

- `GET /assessment-types`
  - Query: `limit`, `offset`
  - Returns paginated assessment type records.

### Exams

- `GET /exams`
  - Query: `limit`, `offset`
  - Returns paginated exam records.
- `POST /exams`
  - Creates exam.
- `GET /exams/{exam_id}`
  - Returns one exam.
- `PATCH /exams/{exam_id}`
  - Partially updates exam metadata.

### Exam Versions

- `POST /exams/{exam_id}/versions`
  - Creates an exam version under an exam.
- `GET /exam-versions/{version_id}`
  - Returns one exam version.
- `PATCH /exam-versions/{version_id}`
  - Updates a version only while status is not `PUBLISHED`.
- `POST /exam-versions/{version_id}/publish`
  - Performs state transition `DRAFT -> PUBLISHED`.

### Question Banks

- `GET /question-banks`
  - Query: `limit`, `offset`
  - Returns paginated question banks.
- `POST /question-banks`
  - Creates question bank.

### Questions

- `GET /questions`
  - Query: `limit`, `offset`
  - Returns paginated questions.
- `POST /questions`
  - Creates question template.
  - Optional `question_bank_id` can be provided to link question to bank.
- `GET /questions/{question_id}`
  - Returns question data only (does not include expected answer payload).
- `PATCH /questions/{question_id}`
  - Updates question template only if not linked to published exam content.

### Expected Answers

- `POST /questions/{question_id}/expected-answers`
  - Creates a reference solution row for a question.
  - Response is sanitized metadata (no sensitive payload echo).

### Question Grading Profile

- `POST /questions/{question_id}/grading-profile`
  - Creates question-level grading profile.

## Business Rules and Immutability

- Exam version publish transition is restricted to:
  - `DRAFT -> PUBLISHED`
- Publishing from any non-`DRAFT` status returns conflict:
  - HTTP `409`, code `invalid_version_status_transition`
- Published exam versions are immutable:
  - PATCH returns HTTP `409`, code `immutable_published_version`
- Questions linked to published versions are immutable:
  - PATCH returns HTTP `409`, code `immutable_published_content`
- Generic question retrieval endpoint does not expose expected answer payload fields.

## Error Contract

Application errors are returned via API error envelope with stable `code` values such as:

- `exam_not_found`
- `exam_version_not_found`
- `question_not_found`
- `empty_patch`
- `invalid_version_status_transition`
- `immutable_published_version`
- `immutable_published_content`
- `permission_denied`

## Schema Gaps and Notes

- This MVP uses `assessment.question_grading_profile` as primary grading profile table.
- Legacy `assessment.grading_profile` is not used by these endpoints.
- No endpoint currently surfaces `reference_solution.solution_payload` or `solution_payload_json` in read APIs.
- Additional hard validation against enum/domain values is primarily enforced at database layer in this phase.
