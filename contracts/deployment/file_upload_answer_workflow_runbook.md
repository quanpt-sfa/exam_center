# File Upload Answer Workflow Runbook

Workflow assertions:
- question_grading_profile.input_source = SEALED_FILE_REF
- taking-payload.answer_ui.ui_mode = FILE_UPLOAD
- Upload creates `answer_state.FILE_REF`
- Seal snapshot `FILE_REF`
- Missing required file block seal
- Dispatch route `MANUAL_REVIEW_REQUIRED`
- Manual review list contains sealed file answer
- Do not expose expected answer
- Do not expose internal storage key or absolute path

API sequences:
- POST /api/v1/master-data/exam-versions/{exam_version_id}/file-upload-placeholder-question
- GET /api/v1/exam-sessions/{session_id}/taking-payload
- POST /api/v1/submissions/{submission_id}/answers/{generated_exam_question_id}/file
- POST /api/v1/submissions/{submission_id}/seal
- GET /api/v1/grading/manual-review/file-answers
- GET /api/v1/grading/manual-review/file-answers/{sealed_answer_id}/content
- POST /api/v1/grading/manual-review/file-answers/{sealed_answer_id}/score
