# Exam Version Question Authoring API

Base path: `/api/v1`

Endpoints:
- GET /master-data/exam-versions/{exam_version_id}/questions
- POST /master-data/exam-versions/{exam_version_id}/questions
- PATCH /master-data/exam-versions/{exam_version_id}/questions/{question_template_id}

Supported question types:
- `TEXTAREA`
- `TEXTBOX_SQL`
- `FILE_UPLOAD`
- `MCQ_SINGLE`

Authoring rule:
- Do not infer student UI from grading engine name alone.
