# Question Grading Profile API

Base path: `/api/v1`

Endpoints:
- GET `/master-data/exam-versions/{exam_version_id}/question-grading-profiles`
- POST `/master-data/exam-versions/{exam_version_id}/question-grading-profiles`
- PATCH `/master-data/question-grading-profiles/{question_grading_profile_id}`
- POST `/master-data/question-grading-profiles/{question_grading_profile_id}/retire`
- POST `/master-data/exam-versions/{exam_version_id}/file-upload-placeholder-question`
- POST `/master-data/exam-versions/{exam_version_id}/configure-file-upload-manual-grading`

Policy notes:
- File upload manual review uses `MANUAL_RUBRIC`.
- Direct file upload questions use `SEALED_FILE_REF`.
