# Delivery and Submission API MVP

Tài liệu này định nghĩa contract runtime Delivery + Submission cho luồng làm bài sinh viên.

## Base path
Tất cả endpoint nằm dưới `/api/v1`.

## Mô hình truy cập
- Student chỉ truy cập session/submission của chính mình.
- Staff theo role policy backend (`PROCTOR`, `INSTRUCTOR`, `ADMIN`, `ACADEMIC_OFFICER`).

## Delivery endpoints chính
- `GET /exam-sessions`
- `GET /exam-sessions/{session_id}`
- `GET /exam-sessions/{session_id}/runtime`
- `GET /exam-sessions/{session_id}/taking-payload`
- `GET /exam-sessions/{session_id}/paper`
- `GET /exam-sessions/{session_id}/paper-assets`
- `GET /exam-sessions/{session_id}/paper-assets/{paper_asset_id}/content`
- `POST /exam-sessions/{session_id}/start`
- `GET /exam-sessions/{session_id}/timer`
- `POST /exam-sessions/{session_id}/heartbeat`
- `POST /exam-sessions/{session_id}/device-bind`

## Submission endpoints chính
- `POST /submissions/{submission_id}/answers/autosave`
- `GET /submissions/{submission_id}/answers/state`
- `POST /submissions/{submission_id}/answers/{generated_exam_question_id}/file`
- `GET /submissions/{submission_id}/answers/{generated_exam_question_id}/file`
- `GET /submissions/{submission_id}/answers/{generated_exam_question_id}/file/content`
- `DELETE /submissions/{submission_id}/answers/{generated_exam_question_id}/file`
- `POST /submissions/{submission_id}/seal`
- `GET /submissions/{submission_id}/seal`

## Student runtime payload (rút gọn)

Frontend nên dùng endpoint backend-resolved:

`GET /exam-sessions/{session_id}/runtime`

`GET /exam-sessions/{session_id}/taking-payload` được giữ làm alias/contract cũ để không phá frontend hoặc test cũ.

```json
{
  "runtime_contract": {
    "contract_name": "student_exam_runtime",
    "contract_version": "2026-05-16",
    "answer_key_policy": "ANSWER_KEYS_NEVER_INCLUDED",
    "rendering_source": "RESOLVED_RESPONSE_PROFILE"
  },
  "session": {},
  "submission": {
    "exam_submission_id": 12001
  },
  "paper": {
    "questions": [
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
          "current_file": null
        },
        "response_profile": {
          "ui_mode": "FILE_UPLOAD",
          "input_source": "SEALED_FILE_REF",
          "answer_format": "FILE_REF",
          "required": true,
          "external_work_required": false,
          "capture_required": false
        },
        "student_grading_profile": {
          "input_source": "SEALED_FILE_REF",
          "answer_language": "NONE",
          "grading_engine_code": "MANUAL_RUBRIC",
          "comparison_method": "MANUAL_RUBRIC",
          "manual_review_policy": "ALWAYS",
          "max_score": 10
        },
        "capture_profile": {
          "requires_capture": false,
          "required_capture_type": null
        }
      }
    ]
  },
  "timer": {}
}
```

## Quy tắc render runtime
- `response_profile` là contract an toàn mới cho frontend render input.
- `answer_ui` vẫn tồn tại để tương thích với frontend hiện có.
- UI mode phải resolve từ profile backend (delivery profile + question grading profile), không suy diễn từ tên đề/tên file/tên môn.
- Không suy diễn form làm bài chỉ từ `grading_engine_code` hoặc `comparison_method`.

Mapping chuẩn từ `question_grading_profile.input_source`:
- `SEALED_TEXT_ANSWER` -> `TEXTAREA` hoặc `CODE_EDITOR`
- `SEALED_JSON_ANSWER` -> `JSON_EDITOR`
- `SEALED_FILE_REF` -> `FILE_UPLOAD`
- `STUDENT_DATABASE_CAPTURE`/`MISA_DATABASE_CAPTURE`/`AMIS_API_CAPTURE` -> `INSTRUCTION_ONLY`
- `MANUAL` -> `MANUAL_RESPONSE` hoặc `INSTRUCTION_ONLY` (không phải direct file upload)

## Làm rõ 3 loại artifact
1. Visual paper asset:
   - PDF/ảnh hiển thị đề cho sinh viên.
   - Gắn với `assessment.exam_version`.
   - Không định nghĩa answer input, không định nghĩa grading engine, không tự tạo câu hỏi.
2. Student answer file asset:
   - Tệp bài làm sinh viên nộp theo câu hỏi.
   - Gắn với submission/question runtime; lưu dưới dạng `FILE_REF`.
3. Capture artifact:
   - Artifact thu thập sau seal bởi capture flow, dùng cho exam kiểu database/software capture.

## Security contract
- Không lộ expected answers trong payload sinh viên.
- Không lộ internal storage path trong JSON.
- Không cho browser gọi worker/database trực tiếp.
