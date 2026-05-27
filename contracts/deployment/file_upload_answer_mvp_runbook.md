# File Upload Answer MVP Runbook

Scope:
- Visual paper asset
- Student answer file asset
- Capture artifact

API-first sequence:
- POST /api/v1/master-data/exams/{exam_id}/versions/{exam_version_id}/paper-assets
- PUT /api/v1/master-data/exam-versions/{exam_version_id}/delivery-profile
- POST /api/v1/master-data/exam-versions/{exam_version_id}/question-grading-profiles
- POST /api/v1/delivery/setup/sittings
- GET /api/v1/exam-sessions/{session_id}/taking-payload
- POST /api/v1/submissions/{submission_id}/answers/{generated_exam_question_id}/file
- POST /api/v1/submissions/{submission_id}/seal
- GET /api/v1/grading/manual-review/file-answers
- GET /api/v1/grading/manual-review/file-answers/{sealed_answer_id}/content
- POST /api/v1/grading/manual-review/file-answers/{sealed_answer_id}/score

Boundary rules:
- Frontend only calls backend `/api/v1`.
- Frontend does not call worker or database directly.

Outcome labels:
- Submit by attached file
- Manual rubric review
