# File Answer Submission API Contract (MVP)

Base path: `/api/v1`

## Phân tách khái niệm
1. Visual paper asset:
   - PDF/ảnh hiển thị đề thi cho sinh viên.
   - Gắn với `assessment.exam_version`.
   - Không định nghĩa answer input, không định nghĩa grading engine, không tự tạo câu hỏi.
2. Student answer file asset:
   - Tệp sinh viên nộp làm bài.
   - Gắn với `submission/exam_submission/generated_exam_question`.
   - Biểu diễn trong answer state bằng `answer_type = FILE_REF`.
   - Được snapshot sang `sealed_answer` khi seal.
3. Capture artifact:
   - Artifact được tạo sau seal bởi capture pipeline.
   - Dùng cho bài thi dạng capture/database; khác với upload file trực tiếp của sinh viên.

## Authorization + security
- Student chỉ truy cập submission của mình.
- Staff theo role policy backend.
- Không lộ filesystem path/storage key trong JSON response.
- Không lộ expected answers/reference solutions.
- File upload là private evidence, không public static.
- Sau seal, upload/replace/delete phải bị từ chối rõ ràng.

## Error codes tối thiểu
- `SUBMISSION_NOT_FOUND`
- `SUBMISSION_NOT_OWNED`
- `SUBMISSION_ALREADY_SEALED`
- `QUESTION_NOT_FOUND`
- `QUESTION_NOT_FILE_UPLOAD`
- `FILE_TOO_LARGE`
- `UNSUPPORTED_FILE_TYPE`
- `FILE_UPLOAD_NOT_CONFIGURED`
- `FILE_STORAGE_ERROR`

## Endpoints
1. `POST /submissions/{submission_id}/answers/{generated_exam_question_id}/file`
2. `GET /submissions/{submission_id}/answers/{generated_exam_question_id}/file`
3. `GET /submissions/{submission_id}/answers/{generated_exam_question_id}/file/content`
4. `DELETE /submissions/{submission_id}/answers/{generated_exam_question_id}/file`
5. `POST /submissions/{submission_id}/seal`

## Contract nộp file theo câu
- Nguồn answer input cho direct file upload phải là `SEALED_FILE_REF`.
- Không dùng `MANUAL` làm `input_source` cho direct file upload.
- `MANUAL_RUBRIC` là phương thức chấm (`grading_engine_code`/`comparison_method`), không phải input source.
- Metadata khuyến nghị:
  - `metadata_json.answer_format = FILE_REF`
  - `metadata_json.manual_review_policy = ALWAYS`

## Canonical file policy (backend authoritative)
- Allowed extensions:
  - `.zip`, `.pdf`, `.docx`, `.xlsx`, `.csv`, `.sql`, `.txt`, `.json`
- Allowed MIME by extension:
  - `.zip`: `application/zip`, `application/x-zip-compressed`
  - `.pdf`: `application/pdf`
  - `.docx`: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  - `.xlsx`: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
  - `.csv`: `text/csv`, `application/csv`, `text/plain`
  - `.sql`: `application/sql`, `text/plain`, `application/octet-stream`
  - `.txt`: `text/plain`
  - `.json`: `application/json`, `text/json`
- Dangerous extensions must be rejected:
  - `.exe`, `.bat`, `.cmd`, `.ps1`, `.msi`, `.scr`, `.js`, `.vbs`, `.jar`, `.com`, `.dll`
- Validation notes:
  - Backend does not trust client-only MIME.
  - For strict binary types (`.pdf`, `.zip`, `.docx`, `.xlsx`), signature validation is required.
  - For safe text-like types (`.csv`, `.sql`, `.txt`, `.json`), `text/plain` is allowed when extension matches.

## Student runtime/taking payload extension
Với câu hỏi nộp file, runtime payload cần `response_profile` và `answer_ui` tương thích ngược như sau:

```json
{
  "generated_exam_question_id": 1001,
  "question_order": 1,
  "question_type": "FILE_UPLOAD",
  "rendered_question_text": "Đính kèm bài làm",
  "score": 10,
  "answer_ui": {
    "ui_mode": "FILE_UPLOAD",
    "input_source": "SEALED_FILE_REF",
    "answer_format": "FILE_REF",
    "required": true,
    "allowed_mime_types": [
      "application/zip",
      "application/x-zip-compressed",
      "application/pdf",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "text/csv",
      "application/csv",
      "application/sql",
      "text/plain",
      "application/octet-stream",
      "application/json",
      "text/json"
    ],
    "allowed_extensions": [
      ".zip",
      ".pdf",
      ".docx",
      ".xlsx",
      ".csv",
      ".sql",
      ".txt",
      ".json"
    ],
    "max_file_size_bytes": 26214400,
    "current_file": {
      "file_asset_id": 123,
      "original_filename": "bai_lam.zip",
      "mime_type": "application/zip",
      "file_size_bytes": 1000,
      "sha256_hash": "6ef2b6c0ec5f3fd6f4de64f27a65f5af4f5a1041fce91f9837d9a2d7f6fcfc19"
    }
  },
  "response_profile": {
    "ui_mode": "FILE_UPLOAD",
    "input_source": "SEALED_FILE_REF",
    "answer_format": "FILE_REF",
    "required": true,
    "allowed_extensions": [".zip", ".pdf", ".docx", ".xlsx", ".csv", ".sql", ".txt", ".json"],
    "allowed_mime_types": ["application/zip", "application/pdf", "text/plain"],
    "max_file_size_bytes": 26214400,
    "external_work_required": false,
    "capture_required": false
  },
  "student_grading_profile": {
    "grading_engine_code": "MANUAL_RUBRIC",
    "comparison_method": "MANUAL_RUBRIC",
    "manual_review_policy": "ALWAYS",
    "max_score": 10
  }
}
```

## Seal contract
- Seal phải reject nếu câu hỏi bắt buộc có `input_source = SEALED_FILE_REF` nhưng không có `FILE_REF` hợp lệ trong `answer_state`.
- Seal idempotent cho lần gọi lặp lại.
- Seal snapshot reference file sang `sealed_answer`.

## Dispatch contract
- Submission đã seal, đủ `FILE_REF` bắt buộc, và profile chấm `MANUAL_RUBRIC` phải route sang `MANUAL_REVIEW_REQUIRED` (hoặc queue manual-grading tương đương), không phải `NOT_READY`.

## Nội dung không được lộ ra frontend
- `expected_answer`, `generated_expected_answer`, `reference_solution`, `solution_sql`
- internal storage key và absolute filesystem path
