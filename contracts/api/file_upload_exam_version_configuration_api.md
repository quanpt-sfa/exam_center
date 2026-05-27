# File Upload Exam Version Configuration API

Base path: `/api/v1`

Endpoint:
- POST /master-data/exam-versions/{exam_version_id}/configure-file-upload-manual-grading

Configuration notes:
- Delivery stays `FILE_BASED`.
- Visual paper uses `FILE_ARTIFACT`.
- Student upload grading uses `SEALED_FILE_REF`.
- Manual review uses `MANUAL_RUBRIC`.

Storage boundary examples:
- `storage_relative_path` may exist in internal storage metadata only.
- `internal_storage_key` may exist in internal storage metadata only.
