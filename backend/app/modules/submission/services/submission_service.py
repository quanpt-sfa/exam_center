"""Service layer for submission autosave and seal APIs."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
import mimetypes
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext

from app.core.errors import ApiError
from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.infrastructure.storage.answer_files import (
    STRICT_BINARY_SIGNATURE_EXTENSIONS,
    allowed_mimes_for_extension,
    detect_mime_type_by_signature,
    file_extension,
    get_answer_file_max_bytes,
    internal_storage_key_for_upload,
    is_dangerous_extension,
    normalized_allowed_extensions,
    normalized_allowed_mimes,
    preferred_mime_for_extension,
    resolve_answer_storage_path,
    sanitize_original_filename,
    stored_filename_for_upload,
)
from app.modules.submission.mappers.submission_mapper import (
    map_answer_file_asset_row,
    map_answer_state_row,
    map_save_item_row,
    map_seal_summary_row,
)
from app.modules.submission.repositories.submission_repository import SubmissionRepository
from app.modules.submission.services.submission_dispatch_readiness_service import (
    SubmissionDispatchReadinessService,
    build_submission_dispatch_readiness_service,
)
from app.modules.submission.seal_contract import (
    ALLOWED_SEAL_REASONS,
    FORCE_SEAL_REASONS,
    SEAL_CONTRACT_VERSION,
    build_seal_response,
    build_dispatch_contract,
    normalize_seal_reason,
    status_for_seal_reason,
)


_STUDENT_ALLOWED_SEAL_REASONS = {"STUDENT_SUBMIT"}
_SEALED_STATES = {"SEALED", "SUPERSEDED", "VOIDED"}
_ADMIN_LIKE_ROLES = {"ADMIN", "ACADEMIC_OFFICER", "INSTRUCTOR"}
_PROCTOR_ROLES = {"PROCTOR"}
_STUDENT_SUBMITTABLE_SESSION_STATUSES = {"IN_PROGRESS", "PAUSED", "INTERRUPTED"}
_SUBMISSION_CONTEXT_ALLOWED_KEYS = {
    "source",
    "client_request_id",
    "ui_source",
    "smoke_run_id",
    "operator_note_tag",
    "reason_hint",
}
_SUBMISSION_CONTEXT_SENSITIVE_TERMS = (
    "token",
    "refresh",
    "access",
    "password",
    "secret",
    "cookie",
    "authorization",
    "auth",
    "session",
    "header",
    "payload",
)
_SUBMISSION_CONTEXT_MAX_STRING_LENGTH = 200
_EXTERNAL_INPUT_SOURCES = {
    "STUDENT_DATABASE_CAPTURE",
    "MISA_DATABASE_CAPTURE",
    "AMIS_API_CAPTURE",
    "FILE_ARTIFACT_CAPTURE",
}
_READY_RUNTIME_MODALITIES = {"FORM_TEXTBOX", "TEXTBOX_SQL", "TEXTBOX_CODE", "FILE_BASED"}



class SubmissionService:
    """Business orchestration for submission APIs."""

    def __init__(
        self,
        repository: SubmissionRepository | None = None,
        transaction_scope: Callable[[], AbstractContextManager[object]] | None = None,
        dispatch_readiness_service: SubmissionDispatchReadinessService | None = None,
    ) -> None:
        self.repository = repository or SubmissionRepository()
        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif repository is None:
            self._transaction_scope = database_unit_of_work
        else:
            self._transaction_scope = nullcontext

        if dispatch_readiness_service is not None:
            self._dispatch_readiness_service = dispatch_readiness_service
        elif repository is None:
            self._dispatch_readiness_service = build_submission_dispatch_readiness_service()
        else:
            self._dispatch_readiness_service = None

    @staticmethod
    def _roles(current_user: dict) -> set[str]:
        return {str(role).upper() for role in current_user.get("roles", [])}

    def _assert_submission_access(self, submission_row: dict, current_user: dict) -> None:
        roles = self._roles(current_user)
        if roles.intersection(_ADMIN_LIKE_ROLES):
            return

        if roles.intersection(_PROCTOR_ROLES):
            actor_user_id = current_user.get("user_id")
            room_id = submission_row.get("exam_sitting_room_id")
            if actor_user_id is None or room_id is None:
                raise ApiError(
                    status_code=403,
                    code="permission_denied",
                    message="Proctor is not assigned to this room",
                    details={"exam_submission_id": int(submission_row["exam_submission_id"])} ,
                )
            if not hasattr(self.repository, "is_proctor_assigned_to_room"):
                raise ApiError(
                    status_code=403,
                    code="permission_denied",
                    message="Proctor is not assigned to this room",
                    details={"exam_submission_id": int(submission_row["exam_submission_id"])} ,
                )
            if not self.repository.is_proctor_assigned_to_room(
                exam_sitting_room_id=int(room_id),
                proctor_user_id=int(actor_user_id),
            ):
                raise ApiError(
                    status_code=403,
                    code="permission_denied",
                    message="Proctor is not assigned to this room",
                    details={
                        "exam_submission_id": int(submission_row["exam_submission_id"]),
                        "exam_sitting_room_id": int(room_id),
                    },
                )
            return

        if "STUDENT" not in roles:
            return

        raw_user_id = current_user.get("user_id")
        try:
            actor_user_id = int(raw_user_id)
        except (TypeError, ValueError):
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Insufficient permissions",
                details={"exam_submission_id": int(submission_row["exam_submission_id"])},
            )

        actor_student_id = self.repository.get_student_id_by_user_id(actor_user_id)
        if actor_student_id is None or actor_student_id != int(submission_row["student_id"]):
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Student cannot access another student's submission",
                details={"exam_submission_id": int(submission_row["exam_submission_id"])},
            )

    def _get_submission_or_404(self, submission_id: int) -> dict:
        row = self.repository.get_submission_by_id(submission_id)
        if row is None:
            raise ApiError(
                status_code=404,
                code="submission_not_found",
                message="Submission not found",
                details={"exam_submission_id": submission_id},
            )
        return row

    @staticmethod
    def _metadata_json(value: dict | None) -> dict:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        return {}

    @staticmethod
    def _normalize_note(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return text[:1000]

    @classmethod
    def _contains_sensitive_key(cls, key: str) -> bool:
        lowered = key.strip().lower()
        return any(term in lowered for term in _SUBMISSION_CONTEXT_SENSITIVE_TERMS)

    @classmethod
    def _sanitize_context_value(cls, value: object, *, depth: int = 0) -> Any:
        if value is None:
            return None
        if isinstance(value, bool | int | float):
            return value
        if isinstance(value, str):
            text = value.strip()
            return text[:_SUBMISSION_CONTEXT_MAX_STRING_LENGTH]
        if depth >= 2:
            return None
        if isinstance(value, list | tuple):
            items: list[Any] = []
            for item in value[:10]:
                sanitized = cls._sanitize_context_value(item, depth=depth + 1)
                if sanitized is not None:
                    items.append(sanitized)
            return items
        if isinstance(value, Mapping):
            sanitized_map: dict[str, Any] = {}
            for raw_key, raw_value in value.items():
                key = str(raw_key).strip()
                if not key or cls._contains_sensitive_key(key):
                    continue
                sanitized = cls._sanitize_context_value(raw_value, depth=depth + 1)
                if sanitized is None:
                    continue
                sanitized_map[key[:80]] = sanitized
            return sanitized_map
        return None

    @classmethod
    def _sanitize_submission_context(cls, value: object) -> dict[str, Any] | None:
        if not isinstance(value, Mapping):
            return None
        sanitized: dict[str, Any] = {}
        for key in _SUBMISSION_CONTEXT_ALLOWED_KEYS:
            if key not in value:
                continue
            item = cls._sanitize_context_value(value[key])
            if item is not None:
                sanitized[key] = item
        return sanitized or None

    @staticmethod
    def _actor_role(current_user: dict) -> str:
        roles = {str(role).upper() for role in current_user.get("roles", [])}
        for role in ("ADMIN", "ACADEMIC_OFFICER", "INSTRUCTOR", "PROCTOR", "STUDENT"):
            if role in roles:
                return role
        return "UNKNOWN"

    @staticmethod
    def _history_action_type(*, submission_status: str, seal_reason: str) -> str:
        normalized_status = str(submission_status).strip().upper()
        normalized_reason = str(seal_reason).strip().upper()
        if normalized_reason == "STUDENT_SUBMIT" or normalized_status == "SUBMITTED":
            return "SUBMITTED"
        if normalized_status == "EXPIRED_SEALED":
            return "EXPIRED_SEALED"
        if normalized_status == "FORCE_SEALED":
            return "FORCE_SEALED"
        return "AUTO_SUBMITTED"

    def _load_runtime_policy_context(self, *, submission: dict) -> dict:
        if hasattr(self.repository, "get_submission_runtime_policy_context"):
            context = self.repository.get_submission_runtime_policy_context(int(submission["exam_submission_id"]))
            if context is not None:
                return context
        return dict(submission)

    def _lock_submission_runtime_context(self, submission_id: int) -> dict:
        if hasattr(self.repository, "lock_submission_runtime_policy_context"):
            context = self.repository.lock_submission_runtime_policy_context(int(submission_id))
            if context is not None:
                return context
        return self._get_submission_or_404(int(submission_id))

    def _assert_student_submit_eligible(self, *, submission_context: dict) -> None:
        room_status = str(submission_context.get("room_status") or "").strip().upper()
        if room_status == "CLOSED":
            raise ApiError(
                status_code=409,
                code="exam_sitting_room_closed",
                message="Submission is blocked because the sitting room is closed",
                details={
                    "exam_submission_id": int(submission_context["exam_submission_id"]),
                    "exam_sitting_room_id": int(submission_context["exam_sitting_room_id"]) if submission_context.get("exam_sitting_room_id") is not None else None,
                },
            )

        session_status = str(submission_context.get("session_status") or "").strip().upper()
        if session_status and session_status not in _STUDENT_SUBMITTABLE_SESSION_STATUSES:
            raise ApiError(
                status_code=409,
                code="submission_not_eligible",
                message="Submission is not eligible from the current session state",
                details={
                    "exam_submission_id": int(submission_context["exam_submission_id"]),
                    "session_status": session_status,
                    "allowed_session_statuses": sorted(_STUDENT_SUBMITTABLE_SESSION_STATUSES),
                },
            )

        deadline_at = submission_context.get("deadline_at")
        if deadline_at is not None and deadline_at <= datetime.now(timezone.utc):
            raise ApiError(
                status_code=409,
                code="submission_window_expired",
                message="Submission window has expired",
                details={
                    "exam_submission_id": int(submission_context["exam_submission_id"]),
                    "deadline_at": deadline_at,
                },
            )

    def _record_submission_history(
        self,
        *,
        submission_id: int,
        exam_session_id: int | None,
        current_user: dict,
        from_status: str | None,
        to_status: str,
        seal_reason: str,
        note: str | None,
        idempotency_key: str | None,
        context_json: dict[str, Any] | None,
    ) -> None:
        if not hasattr(self.repository, "insert_submission_history"):
            return
        actor_user_id = current_user.get("user_id")
        self.repository.insert_submission_history(
            exam_submission_id=int(submission_id),
            exam_session_id=int(exam_session_id) if exam_session_id is not None else None,
            actor_user_id=int(actor_user_id) if actor_user_id is not None else None,
            actor_role=self._actor_role(current_user),
            action_type=self._history_action_type(submission_status=to_status, seal_reason=seal_reason),
            from_status=(str(from_status).strip().upper() if from_status else None),
            to_status=str(to_status).strip().upper(),
            reason_code=str(seal_reason).strip().upper(),
            note=note,
            context_json=context_json,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def _normalize_content_type(value: str | None) -> str | None:
        text = str(value or "").strip().lower()
        if not text:
            return None
        return text.split(";")[0].strip() or None

    def _question_file_policy(self, question_row: dict) -> dict:
        payload = question_row.get("rendered_question_payload_json")
        answer_ui = payload.get("answer_ui") if isinstance(payload, dict) else None
        answer_ui = answer_ui if isinstance(answer_ui, dict) else {}

        allowed_extensions = normalized_allowed_extensions(answer_ui.get("allowed_extensions"))
        allowed_mimes = normalized_allowed_mimes(answer_ui.get("allowed_mime_types"))
        for ext in allowed_extensions:
            allowed_mimes.update(allowed_mimes_for_extension(ext))

        raw_max_bytes = answer_ui.get("max_file_size_bytes")
        max_file_size_bytes = get_answer_file_max_bytes()
        if raw_max_bytes is not None:
            try:
                candidate = int(raw_max_bytes)
                if candidate > 0:
                    max_file_size_bytes = candidate
            except (TypeError, ValueError):
                pass

        return {
            "answer_ui": answer_ui,
            "allowed_extensions": allowed_extensions,
            "allowed_mimes": allowed_mimes,
            "max_file_size_bytes": max_file_size_bytes,
        }

    def _assert_question_supports_file_upload(self, question_row: dict) -> None:
        question_type = str(question_row.get("question_type") or "").strip().upper()
        payload = question_row.get("rendered_question_payload_json")
        answer_ui = payload.get("answer_ui") if isinstance(payload, dict) else None
        answer_ui = answer_ui if isinstance(answer_ui, dict) else {}
        ui_mode = str(answer_ui.get("ui_mode") or "").strip().upper()
        input_source = str(answer_ui.get("input_source") or "").strip().upper()

        if question_type == "FILE_UPLOAD":
            return

        if ui_mode == "FILE_UPLOAD" and input_source == "SEALED_FILE_REF":
            return

        raise ApiError(
            status_code=422,
            code="QUESTION_NOT_FILE_UPLOAD",
            message="Question does not accept file upload answers",
            details={"generated_exam_question_id": int(question_row["generated_exam_question_id"])},
        )

    def _assert_submission_not_sealed(self, submission_id: int) -> None:
        seal = self.repository.get_seal_by_submission_id(submission_id)
        if seal is None:
            return
        seal_status = str(seal.get("seal_status") or "").strip().upper()
        if seal_status in _SEALED_STATES:
            raise ApiError(
                status_code=409,
                code="SUBMISSION_ALREADY_SEALED",
                message="Submission is already sealed",
                details={"submission_id": int(submission_id)},
            )

    @staticmethod
    def _safe_file_metadata_payload(asset: dict) -> dict:
        return {
            "file_asset_id": int(asset["answer_file_asset_id"]),
            "original_filename": str(asset["original_filename"]),
            "mime_type": str(asset["mime_type"]),
            "file_size_bytes": int(asset["file_size_bytes"]),
            "sha256_hash": str(asset["sha256_hash"]),
        }

    @staticmethod
    def _answer_file_response_payload(asset: dict) -> dict:
        mapped = map_answer_file_asset_row(asset)
        return {
            "submission_id": int(mapped["exam_submission_id"]),
            "generated_exam_question_id": int(mapped["generated_exam_question_id"]),
            "answer_file": {
                "file_asset_id": int(mapped["answer_file_asset_id"]),
                "file_name": mapped["original_filename"],
                "mime_type": mapped["mime_type"],
                "file_size_bytes": int(mapped["file_size_bytes"]),
                "sha256": mapped["sha256_hash"],
                "status": mapped["asset_status"],
                "uploaded_at": mapped["uploaded_at"],
            },
        }

    @staticmethod
    def _detect_effective_mime_type(
        *,
        file_head: bytes,
        extension: str,
        client_content_type: str | None,
    ) -> tuple[str | None, set[str]]:
        detected = detect_mime_type_by_signature(file_head)
        preferred = preferred_mime_for_extension(extension)
        normalized_client = SubmissionService._normalize_content_type(client_content_type)

        candidates: set[str] = set()
        if detected:
            candidates.add(detected)
        if preferred:
            candidates.add(preferred)
        if normalized_client:
            candidates.add(normalized_client)

        if detected == "application/zip" and preferred in {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }:
            return preferred, candidates

        if detected:
            return detected, candidates
        if normalized_client:
            return normalized_client, candidates
        if preferred:
            return preferred, candidates
        guessed, _ = mimetypes.guess_type(f"f{extension}")
        guessed = SubmissionService._normalize_content_type(guessed)
        if guessed:
            candidates.add(guessed)
        return guessed, candidates

    @staticmethod
    async def _write_upload_to_storage(upload_file: UploadFile, storage_path: Path, max_bytes: int) -> dict:
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        digest = sha256()
        total_size = 0
        head = b""
        with storage_path.open("wb") as output:
            while True:
                chunk = await upload_file.read(1024 * 1024)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_bytes:
                    raise ApiError(
                        status_code=413,
                        code="FILE_TOO_LARGE",
                        message="Uploaded file exceeds maximum size",
                        details={"max_file_size_bytes": int(max_bytes)},
                    )
                if len(head) < 512:
                    needed = 512 - len(head)
                    head += chunk[:needed]
                digest.update(chunk)
                output.write(chunk)
        if total_size <= 0:
            raise ApiError(
                status_code=422,
                code="UNSUPPORTED_FILE_TYPE",
                message="Uploaded file is empty",
                details={},
            )
        return {
            "sha256_hash": digest.hexdigest(),
            "file_size_bytes": total_size,
            "file_head": head,
        }

    def assert_submission_access(self, *, submission_id: int, current_user: dict) -> dict:
        submission = self._get_submission_or_404(submission_id)
        self._assert_submission_access(submission, current_user)
        return submission

    def _seal_contract_response(self, *, idempotent: bool, summary_payload: dict) -> dict:
        canonical = build_seal_response(
            submission_id=int(summary_payload["exam_submission_id"]),
            seal_id=int(summary_payload["submission_seal_id"]),
            submission_status=summary_payload.get("submission_status"),
            db_seal_status=str(summary_payload["seal_status"]),
            db_seal_reason=str(summary_payload["seal_reason"]),
            sealed_answer_count=int(summary_payload.get("sealed_answer_count") or 0),
            sealed_at=summary_payload.get("sealed_at"),
            already_sealed=idempotent,
            message=("Submission already sealed" if idempotent else "Submission sealed successfully"),
        )
        canonical_payload = canonical.model_dump(mode="json")

        readiness_payload: dict | None = None
        if self._dispatch_readiness_service is not None:
            readiness_payload = self._dispatch_readiness_service.evaluate_submission(
                submission_id=int(summary_payload["exam_submission_id"])
            )
            canonical_payload["dispatch_ready"] = bool(readiness_payload.get("dispatch_ready"))
            canonical_payload["dispatch_blockers"] = list(readiness_payload.get("blockers") or [])

        dispatch_payload = build_dispatch_contract(
            exam_submission_id=int(summary_payload["exam_submission_id"]),
            submission_seal_id=int(summary_payload["submission_seal_id"]),
            seal_status=str(canonical_payload["seal_status"]),
            sealed_answer_count=int(canonical_payload["sealed_answer_count"]),
        )

        if readiness_payload is not None:
            dispatch_payload.update(
                {
                    "ready": bool(readiness_payload.get("dispatch_ready")),
                    "dispatch_blockers": list(readiness_payload.get("blockers") or []),
                    "dispatch_route": readiness_payload.get("dispatch_route"),
                    "capture_required": bool(readiness_payload.get("capture_required")),
                    "grading_required": bool(readiness_payload.get("grading_required")),
                    "modality": readiness_payload.get("modality"),
                    "exam_version_id": readiness_payload.get("exam_version_id"),
                    "capture_profile_id": readiness_payload.get("capture_profile_id"),
                    "grading_profile_id": readiness_payload.get("grading_profile_id"),
                    "grading_profile_summary": readiness_payload.get("grading_profile_summary"),
                }
            )
            if bool(readiness_payload.get("dispatch_ready")):
                dispatch_payload["next_action"] = "DISPATCH_PENDING"
            elif dispatch_payload.get("dispatch_blockers"):
                dispatch_payload["next_action"] = "BLOCKED_READINESS"

        dispatch_route = readiness_payload.get("dispatch_route") if readiness_payload is not None else None
        return {
            "idempotent": idempotent,
            "seal_contract_version": SEAL_CONTRACT_VERSION,
            **canonical_payload,
            "dispatch_route": dispatch_route,
            "submission_seal_id": int(summary_payload["submission_seal_id"]),
            "exam_submission_id": int(summary_payload["exam_submission_id"]),
            "answer_count": int(summary_payload.get("answer_count") or 0),
            "submission_hash": summary_payload.get("submission_hash"),
            "dispatch": dispatch_payload,
        }

    @staticmethod
    def _is_required_file_question(row: dict) -> bool:
        input_source = str(row.get("input_source") or "").strip().upper()
        if input_source != "SEALED_FILE_REF":
            return False
        payload = row.get("rendered_question_payload_json")
        answer_ui = payload.get("answer_ui") if isinstance(payload, dict) else None
        answer_ui = answer_ui if isinstance(answer_ui, dict) else {}
        profile_meta = row.get("grading_profile_metadata_json") if isinstance(row.get("grading_profile_metadata_json"), dict) else {}
        required_value = answer_ui.get("required")
        if not isinstance(required_value, bool):
            required_value = profile_meta.get("required")
        if not isinstance(required_value, bool):
            required_value = True
        return bool(required_value)

    def _validate_required_file_answers_before_seal(self, *, submission_id: int) -> None:
        rows = self.repository.list_submission_question_seal_requirements(submission_id)
        for row in rows:
            if not self._is_required_file_question(row):
                continue
            answer_type = str(row.get("answer_type") or "").strip().upper()
            payload = row.get("answer_payload_json") if isinstance(row.get("answer_payload_json"), dict) else {}
            file_asset_id = payload.get("file_asset_id")
            active_asset_id = row.get("answer_file_asset_id")
            asset_status = str(row.get("asset_status") or "").strip().upper()
            same_submission = row.get("asset_submission_id") == submission_id
            same_question = row.get("asset_question_id") == row.get("generated_exam_question_id")
            if (
                answer_type != "FILE_REF"
                or file_asset_id is None
                or active_asset_id is None
                or int(file_asset_id) != int(active_asset_id)
                or asset_status != "ACTIVE"
                or not same_submission
                or not same_question
            ):
                raise ApiError(
                    status_code=422,
                    code="REQUIRED_FILE_ANSWER_MISSING",
                    message="Required file upload answer is missing or invalid",
                    details={"generated_exam_question_id": int(row["generated_exam_question_id"])},
                )

    @staticmethod
    def _question_required(row: dict) -> bool:
        payload = row.get("rendered_question_payload_json") if isinstance(row.get("rendered_question_payload_json"), dict) else {}
        answer_ui = payload.get("answer_ui") if isinstance(payload.get("answer_ui"), dict) else {}
        profile_meta = row.get("grading_profile_metadata_json") if isinstance(row.get("grading_profile_metadata_json"), dict) else {}
        required_value = answer_ui.get("required")
        if not isinstance(required_value, bool):
            required_value = profile_meta.get("required")
        if not isinstance(required_value, bool):
            required_value = True
        return bool(required_value)

    @staticmethod
    def _answer_mode_from_requirement_row(row: dict) -> str:
        input_source = str(row.get("input_source") or "").strip().upper()
        question_type = str(row.get("question_type") or "").strip().upper()
        answer_language = str(row.get("answer_language") or "").strip().upper()

        if input_source == "SEALED_FILE_REF" or question_type == "FILE_UPLOAD":
            return "FILE_UPLOAD"
        if input_source == "SEALED_JSON_ANSWER":
            return "JSON"
        if input_source == "SEALED_TEXT_ANSWER":
            if answer_language == "SQL" or question_type == "TEXTBOX_SQL":
                return "SQL_TEXT"
            if question_type == "TEXTBOX_CODE" or answer_language not in {"", "TEXT", "NONE"}:
                return "CODE_TEXT"
            return "TEXT"
        if input_source in _EXTERNAL_INPUT_SOURCES:
            return "READ_ONLY_EXTERNAL"
        return "UNSUPPORTED"

    @staticmethod
    def _unsupported_preflight_item(*, row: dict, severity: str) -> dict:
        question_id = int(row["generated_exam_question_id"])
        input_source = str(row.get("input_source") or "").strip().upper()
        return SubmissionService._make_preflight_item(
            code="UNSUPPORTED_INPUT_SOURCE",
            message="Question input source is not supported for direct student runtime entry",
            severity=severity,
            generated_exam_question_id=question_id,
            details={
                "question_id": question_id,
                "input_source": input_source or None,
            },
        )

    @staticmethod
    def _infer_submission_modality(*, context: dict, rows: list[dict], supported_answer_modes: set[str]) -> str:
        primary_answer_source = str(context.get("primary_answer_source") or "").strip().upper()
        if primary_answer_source == "STUDENT_DATABASE_CAPTURE":
            return "STUDENT_DATABASE"
        if primary_answer_source == "MISA_DATABASE_CAPTURE":
            return "MISA_DATABASE"
        if primary_answer_source == "AMIS_API_CAPTURE":
            return "AMIS_ONLINE"

        direct_modes = {mode for mode in supported_answer_modes if mode not in {"READ_ONLY_EXTERNAL", "UNSUPPORTED"}}
        has_external = any(SubmissionService._answer_mode_from_requirement_row(row) == "READ_ONLY_EXTERNAL" for row in rows)
        if has_external and direct_modes:
            return "HYBRID"
        if has_external:
            if any(str(row.get("input_source") or "").strip().upper() == "STUDENT_DATABASE_CAPTURE" for row in rows):
                return "STUDENT_DATABASE"
            if any(str(row.get("input_source") or "").strip().upper() == "MISA_DATABASE_CAPTURE" for row in rows):
                return "MISA_DATABASE"
            if any(str(row.get("input_source") or "").strip().upper() == "AMIS_API_CAPTURE" for row in rows):
                return "AMIS_ONLINE"
            return "FOUNDATION_ONLY"
        if direct_modes == {"FILE_UPLOAD"}:
            return "FILE_BASED"
        if direct_modes and direct_modes.issubset({"SQL_TEXT"}):
            return "TEXTBOX_SQL"
        if direct_modes and direct_modes.issubset({"CODE_TEXT"}):
            return "TEXTBOX_CODE"
        return "FORM_TEXTBOX"

    @staticmethod
    def _runtime_readiness_for_modality(modality: str) -> str:
        return "READY" if modality in _READY_RUNTIME_MODALITIES else "FOUNDATION_ONLY"

    @staticmethod
    def _make_preflight_item(
        *,
        code: str,
        message: str,
        severity: str,
        generated_exam_question_id: int | None = None,
        details: dict | None = None,
    ) -> dict:
        return {
            "code": code,
            "message": message,
            "severity": severity,
            "generated_exam_question_id": generated_exam_question_id,
            "details": details or {},
        }

    @classmethod
    def _row_has_required_answer(cls, row: dict, *, answer_mode: str) -> bool:
        answer_type = str(row.get("answer_type") or "").strip().upper()
        answer_text = str(row.get("answer_text") or "")
        payload = row.get("answer_payload_json") if isinstance(row.get("answer_payload_json"), dict) else None

        if answer_mode in {"TEXT", "SQL_TEXT", "CODE_TEXT"}:
            return bool(answer_text.strip())
        if answer_mode == "JSON":
            if payload:
                return True
            return bool(answer_text.strip())
        if answer_mode == "FILE_UPLOAD":
            file_asset_id = payload.get("file_asset_id") if isinstance(payload, dict) else None
            active_asset_id = row.get("answer_file_asset_id")
            asset_status = str(row.get("asset_status") or "").strip().upper()
            same_submission = row.get("asset_submission_id") == row.get("submission_id")
            same_question = row.get("asset_question_id") == row.get("generated_exam_question_id")
            return (
                answer_type == "FILE_REF"
                and file_asset_id is not None
                and active_asset_id is not None
                and int(file_asset_id) == int(active_asset_id)
                and asset_status == "ACTIVE"
                and same_submission
                and same_question
            )
        return False

    def _evaluate_seal_preflight(self, *, submission_id: int, submission_context: dict | None = None) -> dict:
        context_loader = getattr(self.repository, "get_submission_runtime_contract_context", None)
        if submission_context is None and callable(context_loader):
            submission_context = context_loader(int(submission_id))
        if submission_context is None:
            submission_context = self._get_submission_or_404(int(submission_id))

        rows = self.repository.list_submission_question_seal_requirements(int(submission_id))
        blockers: list[dict] = []
        warnings: list[dict] = []
        supported_answer_modes: set[str] = set()
        required_questions = 0
        completed_required_questions = 0
        uploaded_file_questions = 0

        existing_seal = self.repository.get_seal_by_submission_id(int(submission_id))
        if existing_seal is not None and str(existing_seal.get("seal_status") or "").strip().upper() in _SEALED_STATES:
            blockers.append(
                self._make_preflight_item(
                    code="ALREADY_SEALED",
                    message="Submission is already sealed",
                    severity="blocker",
                    details={"submission_seal_id": int(existing_seal["submission_seal_id"])},
                )
            )

        room_status = str(submission_context.get("room_status") or "").strip().upper()
        if room_status == "CLOSED":
            blockers.append(
                self._make_preflight_item(
                    code="ROOM_CLOSED",
                    message="Exam room is closed",
                    severity="blocker",
                    details={"room_status": room_status},
                )
            )

        deadline_at = submission_context.get("deadline_at")
        if deadline_at is not None and deadline_at <= datetime.now(timezone.utc):
            blockers.append(
                self._make_preflight_item(
                    code="DEADLINE_EXPIRED",
                    message="Submission window has expired",
                    severity="blocker",
                    details={"deadline_at": deadline_at},
                )
            )

        session_status = str(submission_context.get("session_status") or "").strip().upper()
        if session_status and session_status not in _STUDENT_SUBMITTABLE_SESSION_STATUSES:
            blockers.append(
                self._make_preflight_item(
                    code="SESSION_NOT_ELIGIBLE",
                    message="Submission is not eligible from the current session state",
                    severity="blocker",
                    details={"session_status": session_status},
                )
            )

        for row in rows:
            row["submission_id"] = int(submission_id)
            answer_mode = self._answer_mode_from_requirement_row(row)
            supported_answer_modes.add(answer_mode)
            if answer_mode == "FILE_UPLOAD" and row.get("answer_file_asset_id") is not None:
                uploaded_file_questions += 1

            if answer_mode == "UNSUPPORTED":
                if self._question_required(row):
                    required_questions += 1
                    blockers.append(self._unsupported_preflight_item(row=row, severity="blocker"))
                else:
                    warnings.append(self._unsupported_preflight_item(row=row, severity="warning"))
                continue

            if not self._question_required(row):
                continue

            required_questions += 1
            if self._row_has_required_answer(row, answer_mode=answer_mode):
                completed_required_questions += 1
                continue

            question_id = int(row["generated_exam_question_id"])
            if answer_mode in {"TEXT", "SQL_TEXT", "CODE_TEXT"}:
                blockers.append(
                    self._make_preflight_item(
                        code="REQUIRED_TEXT_MISSING",
                        message="Required text answer is missing",
                        severity="blocker",
                        generated_exam_question_id=question_id,
                    )
                )
            elif answer_mode == "JSON":
                blockers.append(
                    self._make_preflight_item(
                        code="REQUIRED_JSON_MISSING",
                        message="Required JSON answer is missing",
                        severity="blocker",
                        generated_exam_question_id=question_id,
                    )
                )
            elif answer_mode == "FILE_UPLOAD":
                blockers.append(
                    self._make_preflight_item(
                        code="REQUIRED_FILE_MISSING",
                        message="Required file answer is missing",
                        severity="blocker",
                        generated_exam_question_id=question_id,
                    )
                )

        modality = self._infer_submission_modality(
            context=submission_context,
            rows=rows,
            supported_answer_modes=supported_answer_modes,
        )
        runtime_readiness = self._runtime_readiness_for_modality(modality)
        if modality not in _READY_RUNTIME_MODALITIES:
            blockers.append(
                self._make_preflight_item(
                    code="UNSUPPORTED_MODALITY",
                    message="Submission modality is not supported for direct student runtime in this backend slice",
                    severity="blocker",
                    details={"modality": modality},
                )
            )
            if modality in {"STUDENT_DATABASE", "MISA_DATABASE"}:
                blockers.append(
                    self._make_preflight_item(
                        code="RESOURCE_NOT_READY",
                        message="Runtime resource binding is not ready for this modality",
                        severity="blocker",
                        details={"modality": modality},
                    )
                )
            if modality in {"STUDENT_DATABASE", "MISA_DATABASE", "AMIS_ONLINE", "HYBRID", "FOUNDATION_ONLY"}:
                blockers.append(
                    self._make_preflight_item(
                        code="CAPTURE_NOT_READY",
                        message="Capture-backed grading path is not ready for this modality",
                        severity="blocker",
                        details={"modality": modality},
                    )
                )

        if submission_context.get("session_device_binding_id") is None:
            warnings.append(
                self._make_preflight_item(
                    code="DEVICE_BINDING_MISSING",
                    message="No active station or device binding is currently recorded",
                    severity="warning",
                )
            )

        payload = {
            "exam_submission_id": int(submission_id),
            "can_seal": not blockers,
            "modality": modality,
            "runtime_readiness": runtime_readiness,
            "supported_answer_modes": sorted(mode for mode in supported_answer_modes if mode and mode != "UNSUPPORTED"),
            "counts": {
                "total_questions": len(rows),
                "required_questions": required_questions,
                "completed_required_questions": completed_required_questions,
                "uploaded_file_questions": uploaded_file_questions,
                "pending_uploads": 0,
            },
            "blockers": blockers,
            "warnings": warnings,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        return payload

    def _raise_for_preflight_blockers(self, *, submission_id: int, preflight: dict) -> None:
        blockers = list(preflight.get("blockers") or [])
        if not blockers:
            return

        priority = [
            "ROOM_CLOSED",
            "DEADLINE_EXPIRED",
            "SESSION_NOT_ELIGIBLE",
            "UNSUPPORTED_INPUT_SOURCE",
            "REQUIRED_FILE_MISSING",
            "REQUIRED_TEXT_MISSING",
            "REQUIRED_JSON_MISSING",
            "UNSUPPORTED_MODALITY",
            "RESOURCE_NOT_READY",
            "CAPTURE_NOT_READY",
            "ALREADY_SEALED",
        ]
        selected = blockers[0]
        for code in priority:
            match = next((item for item in blockers if item.get("code") == code), None)
            if match is not None:
                selected = match
                break

        code = str(selected.get("code") or "").strip().upper()
        details = selected.get("details") if isinstance(selected.get("details"), dict) else {}
        if code == "ROOM_CLOSED":
            raise ApiError(
                status_code=409,
                code="exam_sitting_room_closed",
                message="Submission is blocked because the sitting room is closed",
                details={"exam_submission_id": int(submission_id), **details},
            )
        if code == "DEADLINE_EXPIRED":
            raise ApiError(
                status_code=409,
                code="submission_window_expired",
                message="Submission window has expired",
                details={"exam_submission_id": int(submission_id), **details},
            )
        if code == "SESSION_NOT_ELIGIBLE":
            raise ApiError(
                status_code=409,
                code="submission_not_eligible",
                message="Submission is not eligible from the current session state",
                details={"exam_submission_id": int(submission_id), **details},
            )
        if code == "REQUIRED_FILE_MISSING":
            raise ApiError(
                status_code=422,
                code="REQUIRED_FILE_ANSWER_MISSING",
                message="Required file upload answer is missing or invalid",
                details={"generated_exam_question_id": selected.get("generated_exam_question_id")},
            )
        if code == "REQUIRED_TEXT_MISSING":
            raise ApiError(
                status_code=422,
                code="REQUIRED_TEXT_ANSWER_MISSING",
                message="Required text answer is missing",
                details={"generated_exam_question_id": selected.get("generated_exam_question_id")},
            )
        if code == "REQUIRED_JSON_MISSING":
            raise ApiError(
                status_code=422,
                code="REQUIRED_JSON_ANSWER_MISSING",
                message="Required JSON answer is missing",
                details={"generated_exam_question_id": selected.get("generated_exam_question_id")},
            )
        if code == "UNSUPPORTED_INPUT_SOURCE":
            raise ApiError(
                status_code=422,
                code="UNSUPPORTED_INPUT_SOURCE",
                message="Question input source is not supported for direct student runtime entry",
                details={
                    "generated_exam_question_id": selected.get("generated_exam_question_id"),
                    **details,
                },
            )
        if code == "UNSUPPORTED_MODALITY":
            raise ApiError(
                status_code=409,
                code="unsupported_submission_modality",
                message="Submission modality is not supported for direct runtime",
                details=details,
            )
        if code == "RESOURCE_NOT_READY":
            raise ApiError(
                status_code=409,
                code="resource_not_ready",
                message="Runtime resource binding is not ready",
                details=details,
            )
        if code == "CAPTURE_NOT_READY":
            raise ApiError(
                status_code=409,
                code="capture_not_ready",
                message="Capture-backed grading path is not ready",
                details=details,
            )
        if code == "ALREADY_SEALED":
            raise ApiError(
                status_code=409,
                code="SUBMISSION_ALREADY_SEALED",
                message="Submission is already sealed",
                details={"submission_id": int(submission_id), **details},
            )

    def _assert_known_submission_questions(self, *, submission_id: int, generated_exam_question_ids: list[int]) -> None:
        loader = getattr(self.repository, "list_submission_question_ids", None)
        if not callable(loader):
            return
        known_ids = set(loader(int(submission_id)))
        unknown_ids = sorted({int(question_id) for question_id in generated_exam_question_ids} - known_ids)
        if unknown_ids:
            raise ApiError(
                status_code=422,
                code="QUESTION_NOT_FOUND",
                message="One or more questions are not found in submission",
                details={"generated_exam_question_ids": unknown_ids},
            )

    @staticmethod
    def _safe_answer_payload(*, answer_type: str | None, payload: Any) -> Any:
        normalized_answer_type = str(answer_type or "").strip().upper()
        if normalized_answer_type != "MCQ_OPTION" or not isinstance(payload, dict):
            return payload

        safe_payload: dict[str, Any] = {}
        if payload.get("selected_generated_exam_option_id") is not None:
            safe_payload["selected_generated_exam_option_id"] = int(payload["selected_generated_exam_option_id"])
        if isinstance(payload.get("selected_generated_exam_option_ids"), list):
            safe_payload["selected_generated_exam_option_ids"] = [
                int(value) for value in payload["selected_generated_exam_option_ids"] if value is not None
            ]
        return safe_payload

    def _safe_answer_state_row(self, row: dict) -> dict:
        mapped = map_answer_state_row(row)
        mapped["answer_payload_json"] = self._safe_answer_payload(
            answer_type=mapped.get("answer_type"),
            payload=mapped.get("answer_payload_json"),
        )
        return mapped

    @staticmethod
    def _selected_generated_option_ids(payload: dict | None) -> list[int]:
        if not isinstance(payload, dict):
            return []

        selected_single = payload.get("selected_generated_exam_option_id")
        selected_many = payload.get("selected_generated_exam_option_ids")
        values: list[int] = []
        if selected_single is not None:
            try:
                values.append(int(selected_single))
            except (TypeError, ValueError):
                return []
        if isinstance(selected_many, list):
            try:
                values.extend(int(item) for item in selected_many if item is not None)
            except (TypeError, ValueError):
                return []

        deduped: list[int] = []
        for value in values:
            if value > 0 and value not in deduped:
                deduped.append(value)
        return deduped

    def _canonicalize_multiple_choice_answer(self, *, submission_id: int, answer: dict) -> dict:
        question_detail = self.repository.get_submission_question_detail(
            submission_id=int(submission_id),
            generated_exam_question_id=int(answer["generated_exam_question_id"]),
        )
        question_type = str((question_detail or {}).get("question_type") or "").strip().upper()
        answer_type = str(answer.get("answer_type") or "").strip().upper()
        if question_type != "MULTIPLE_CHOICE":
            if answer_type == "MCQ_OPTION":
                raise ApiError(
                    status_code=422,
                    code="invalid_answer_type_for_question",
                    message="MCQ option answers are only allowed for multiple-choice questions",
                    details={"generated_exam_question_id": int(answer["generated_exam_question_id"]), "question_type": question_type or None},
                )
            return answer

        if answer_type != "MCQ_OPTION":
            raise ApiError(
                status_code=422,
                code="invalid_answer_type_for_multiple_choice",
                message="Multiple-choice answers must use MCQ_OPTION answer_type",
                details={"generated_exam_question_id": int(answer["generated_exam_question_id"]), "answer_type": answer_type or None},
            )

        selected_option_ids = self._selected_generated_option_ids(answer.get("answer_payload_json"))
        if not selected_option_ids:
            raise ApiError(
                status_code=422,
                code="invalid_generated_option_selection",
                message="Multiple-choice answers must include a generated option selection",
                details={"generated_exam_question_id": int(answer["generated_exam_question_id"])} ,
            )
        if len(selected_option_ids) > 1:
            raise ApiError(
                status_code=422,
                code="multiple_choice_multi_select_not_supported",
                message="This multiple-choice question only supports a single selected option",
                details={"generated_exam_question_id": int(answer["generated_exam_question_id"]), "selected_generated_exam_option_ids": selected_option_ids},
            )

        generated_exam_option_id = int(selected_option_ids[0])
        option_detail = self.repository.get_generated_option_selection_detail(
            submission_id=int(submission_id),
            generated_exam_question_id=int(answer["generated_exam_question_id"]),
            generated_exam_option_id=generated_exam_option_id,
        )
        if option_detail is None:
            raise ApiError(
                status_code=422,
                code="invalid_generated_option_selection",
                message="Selected option does not belong to this submission question",
                details={
                    "generated_exam_question_id": int(answer["generated_exam_question_id"]),
                    "selected_generated_exam_option_id": generated_exam_option_id,
                },
            )

        normalized_payload = {
            "selected_generated_exam_option_id": generated_exam_option_id,
            "selected_original_option_id": int(option_detail["original_option_id"]),
        }
        return {
            **answer,
            "answer_type": "MCQ_OPTION",
            "answer_text": None,
            "answer_payload_json": normalized_payload,
        }

    def get_seal_preflight(self, *, submission_id: int, current_user: dict) -> dict:
        self.assert_submission_access(submission_id=submission_id, current_user=current_user)
        return self._evaluate_seal_preflight(submission_id=int(submission_id))

    def autosave_answers(self, *, submission_id: int, payload: dict, current_user: dict) -> dict:
        _ = self.assert_submission_access(submission_id=submission_id, current_user=current_user)
        roles = self._roles(current_user)

        idempotency_key = str(payload["idempotency_key"]).strip()
        if not idempotency_key:
            raise ApiError(status_code=400, code="invalid_idempotency_key", message="idempotency_key is required", details={})

        with self._transaction_scope():
            locked_submission = self._lock_submission_runtime_context(int(submission_id))
            if "STUDENT" in roles:
                self._assert_student_submit_eligible(submission_context=locked_submission)
            self._assert_known_submission_questions(
                submission_id=int(submission_id),
                generated_exam_question_ids=[int(answer["generated_exam_question_id"]) for answer in payload["answers"]],
            )

            existing_batch = self.repository.get_batch_by_idempotency(
                submission_id=submission_id,
                idempotency_key=idempotency_key,
            )
            if existing_batch is not None:
                items = self.repository.list_answer_save_items(answer_save_batch_id=int(existing_batch["answer_save_batch_id"]))
                return {
                    "exam_submission_id": submission_id,
                    "batch_status": "DUPLICATE",
                    "idempotent": True,
                    "server_ack_revision": self.repository.get_max_server_revision(submission_id),
                    "items": [map_save_item_row(item) for item in items],
                }

            seal = self.repository.get_seal_by_submission_id(submission_id)
            if seal is not None and str(seal["seal_status"]).upper() in {"SEALED", "SUPERSEDED", "VOIDED"}:
                batch = self.repository.create_answer_save_batch(
                    submission_id=submission_id,
                    idempotency_key=idempotency_key,
                    client_sequence_no=payload.get("client_sequence_no"),
                    client_saved_at=payload.get("client_saved_at"),
                    device_id=payload.get("device_id"),
                    station_id=payload.get("station_id"),
                    batch_status="IGNORED_AFTER_SEAL",
                    accepted_item_count=0,
                    rejected_item_count=len(payload["answers"]),
                    metadata_json=payload.get("metadata_json"),
                )
                items: list[dict] = []
                for answer in payload["answers"]:
                    item = self.repository.create_answer_save_item(
                        answer_save_batch_id=int(batch["answer_save_batch_id"]),
                        generated_exam_question_id=int(answer["generated_exam_question_id"]),
                        answer_state_id=None,
                        client_version=int(answer.get("client_revision") or payload["client_revision"]),
                        server_version=None,
                        answer_hash=answer.get("answer_hash"),
                        answer_length=answer.get("answer_length"),
                        item_status="IGNORED_AFTER_SEAL",
                        error_code="submission_sealed",
                        error_message="Submission already sealed",
                    )
                    items.append(item)

                return {
                    "exam_submission_id": submission_id,
                    "batch_status": "IGNORED_AFTER_SEAL",
                    "idempotent": False,
                    "server_ack_revision": self.repository.get_max_server_revision(submission_id),
                    "items": [map_save_item_row(item) for item in items],
                }

            batch = self.repository.create_answer_save_batch(
                submission_id=submission_id,
                idempotency_key=idempotency_key,
                client_sequence_no=payload.get("client_sequence_no"),
                client_saved_at=payload.get("client_saved_at"),
                device_id=payload.get("device_id"),
                station_id=payload.get("station_id"),
                batch_status="RECEIVED",
                accepted_item_count=0,
                rejected_item_count=0,
                metadata_json=payload.get("metadata_json"),
            )

            accepted = 0
            rejected = 0
            max_ack_revision = self.repository.get_max_server_revision(submission_id)
            result_items: list[dict] = []

            for answer in payload["answers"]:
                try:
                    answer = self._canonicalize_multiple_choice_answer(submission_id=int(submission_id), answer=answer)
                except ApiError as exc:
                    rejected += 1
                    result_items.append(
                        self.repository.create_answer_save_item(
                            answer_save_batch_id=int(batch["answer_save_batch_id"]),
                            generated_exam_question_id=int(answer["generated_exam_question_id"]),
                            answer_state_id=None,
                            client_version=int(answer.get("client_revision") or payload["client_revision"]),
                            server_version=None,
                            answer_hash=answer.get("answer_hash"),
                            answer_length=answer.get("answer_length"),
                            item_status="REJECTED",
                            error_code=exc.code,
                            error_message=exc.message,
                        )
                    )
                    continue

                has_content = (
                    answer.get("answer_text") is not None
                    or answer.get("answer_payload_json") is not None
                    or answer.get("answer_hash") is not None
                )
                if not has_content:
                    rejected += 1
                    result_items.append(
                        self.repository.create_answer_save_item(
                            answer_save_batch_id=int(batch["answer_save_batch_id"]),
                            generated_exam_question_id=int(answer["generated_exam_question_id"]),
                            answer_state_id=None,
                            client_version=int(answer.get("client_revision") or payload["client_revision"]),
                            server_version=None,
                            answer_hash=answer.get("answer_hash"),
                            answer_length=answer.get("answer_length"),
                            item_status="REJECTED",
                            error_code="empty_answer_payload",
                            error_message="Answer content is required",
                        )
                    )
                    continue

                state = self.repository.upsert_answer_state(
                    submission_id=submission_id,
                    generated_exam_question_id=int(answer["generated_exam_question_id"]),
                    answer_type=str(answer["answer_type"]).strip().upper(),
                    answer_text=answer.get("answer_text"),
                    answer_payload_json=answer.get("answer_payload_json"),
                    answer_hash=answer.get("answer_hash"),
                    answer_length=answer.get("answer_length"),
                    client_version=int(answer.get("client_revision") or payload["client_revision"]),
                    client_saved_at=payload.get("client_saved_at"),
                    device_id=payload.get("device_id"),
                    station_id=payload.get("station_id"),
                    metadata_json=answer.get("metadata_json"),
                )
                accepted += 1
                max_ack_revision = max(max_ack_revision, int(state["server_version"]))
                result_items.append(
                    self.repository.create_answer_save_item(
                        answer_save_batch_id=int(batch["answer_save_batch_id"]),
                        generated_exam_question_id=int(answer["generated_exam_question_id"]),
                        answer_state_id=int(state["answer_state_id"]),
                        client_version=int(state["client_version"]),
                        server_version=int(state["server_version"]),
                        answer_hash=state.get("answer_hash"),
                        answer_length=state.get("answer_length"),
                        item_status="APPLIED",
                        error_code=None,
                        error_message=None,
                    )
                )

            if accepted > 0 and rejected > 0:
                batch_status = "PARTIALLY_APPLIED"
            elif accepted > 0:
                batch_status = "APPLIED"
            else:
                batch_status = "REJECTED"

            self.repository.update_answer_save_batch(
                answer_save_batch_id=int(batch["answer_save_batch_id"]),
                batch_status=batch_status,
                accepted_item_count=accepted,
                rejected_item_count=rejected,
            )

            if accepted > 0:
                self.repository.update_submission_after_autosave(submission_id)

            return {
                "exam_submission_id": submission_id,
                "batch_status": batch_status,
                "idempotent": False,
                "server_ack_revision": max_ack_revision,
                "items": [map_save_item_row(item) for item in result_items],
            }

    def get_answer_state(self, *, submission_id: int, current_user: dict) -> dict:
        submission = self.assert_submission_access(submission_id=submission_id, current_user=current_user)

        rows = self.repository.list_answer_state(submission_id)
        return {
            "exam_submission_id": submission_id,
            "server_ack_revision": self.repository.get_max_server_revision(submission_id),
            "items": [self._safe_answer_state_row(row) for row in rows],
        }

    async def upload_answer_file(
        self,
        *,
        submission_id: int,
        generated_exam_question_id: int,
        upload_file: UploadFile,
        metadata_json: dict | None,
        current_user: dict,
    ) -> dict:
        submission = self.assert_submission_access(submission_id=submission_id, current_user=current_user)
        if "STUDENT" in self._roles(current_user):
            submission_context = self._load_runtime_policy_context(submission=submission)
            self._assert_student_submit_eligible(submission_context=submission_context)
        self._assert_submission_not_sealed(submission_id)

        question = self.repository.get_submission_question_detail(
            submission_id=submission_id,
            generated_exam_question_id=generated_exam_question_id,
        )
        if question is None:
            raise ApiError(
                status_code=404,
                code="QUESTION_NOT_FOUND",
                message="Question is not found in submission",
                details={"generated_exam_question_id": int(generated_exam_question_id)},
            )
        self._assert_question_supports_file_upload(question)
        policy = self._question_file_policy(question)
        allowed_extensions = policy["allowed_extensions"]
        allowed_mimes = policy["allowed_mimes"]
        max_file_size_bytes = int(policy["max_file_size_bytes"])

        original_filename = sanitize_original_filename(upload_file.filename)
        extension = file_extension(original_filename)
        if is_dangerous_extension(extension):
            raise ApiError(
                status_code=422,
                code="UNSUPPORTED_FILE_TYPE",
                message="Dangerous file extension is not allowed",
                details={"extension": extension},
            )
        if extension not in allowed_extensions:
            raise ApiError(
                status_code=422,
                code="UNSUPPORTED_FILE_TYPE",
                message="File extension is not allowed",
                details={"extension": extension},
            )

        stored_filename = stored_filename_for_upload(original_filename)
        internal_storage_key = internal_storage_key_for_upload(
            submission_id=submission_id,
            question_id=generated_exam_question_id,
            stored_filename=stored_filename,
        )
        storage_path = resolve_answer_storage_path(internal_storage_key)

        try:
            write_result = await self._write_upload_to_storage(upload_file, storage_path=storage_path, max_bytes=max_file_size_bytes)
            detected_signature_mime = detect_mime_type_by_signature(write_result["file_head"])
            effective_mime_type, mime_candidates = self._detect_effective_mime_type(
                file_head=write_result["file_head"],
                extension=extension,
                client_content_type=upload_file.content_type,
            )
            if effective_mime_type is None:
                raise ApiError(
                    status_code=422,
                    code="UNSUPPORTED_FILE_TYPE",
                    message="File MIME type cannot be determined",
                    details={},
                )

            if extension in STRICT_BINARY_SIGNATURE_EXTENSIONS:
                if extension == ".pdf" and detected_signature_mime != "application/pdf":
                    raise ApiError(
                        status_code=422,
                        code="UNSUPPORTED_FILE_TYPE",
                        message="PDF file signature is invalid",
                        details={"extension": extension},
                    )
                if extension in {".zip", ".docx", ".xlsx"} and detected_signature_mime != "application/zip":
                    raise ApiError(
                        status_code=422,
                        code="UNSUPPORTED_FILE_TYPE",
                        message="Compressed file signature is invalid",
                        details={"extension": extension},
                    )

            extension_allowed_mimes = allowed_mimes_for_extension(extension)
            if extension_allowed_mimes:
                policy_allowed_mimes = extension_allowed_mimes
            else:
                policy_allowed_mimes = set(allowed_mimes)

            if policy_allowed_mimes and not (mime_candidates.intersection(policy_allowed_mimes) or effective_mime_type in policy_allowed_mimes):
                raise ApiError(
                    status_code=422,
                    code="UNSUPPORTED_FILE_TYPE",
                    message="File MIME type is not allowed",
                    details={"mime_type": effective_mime_type},
                )

            actor_user_id = int(current_user["user_id"]) if current_user.get("user_id") is not None else None
            safe_metadata = self._metadata_json(metadata_json)
            self.repository.supersede_active_answer_file_assets(
                submission_id=submission_id,
                generated_exam_question_id=generated_exam_question_id,
                superseded_by=actor_user_id,
            )
            asset = self.repository.create_answer_file_asset(
                submission_id=submission_id,
                generated_exam_question_id=generated_exam_question_id,
                answer_state_id=None,
                original_filename=original_filename,
                stored_filename=stored_filename,
                internal_storage_key=internal_storage_key,
                mime_type=effective_mime_type,
                file_size_bytes=int(write_result["file_size_bytes"]),
                sha256_hash=str(write_result["sha256_hash"]),
                uploaded_by=actor_user_id,
                metadata_json=safe_metadata,
            )

            payload = self._safe_file_metadata_payload(asset)
            answer_state = self.repository.upsert_answer_state(
                submission_id=submission_id,
                generated_exam_question_id=generated_exam_question_id,
                answer_type="FILE_REF",
                answer_text=None,
                answer_payload_json=payload,
                answer_hash=str(write_result["sha256_hash"]),
                answer_length=int(write_result["file_size_bytes"]),
                client_version=max(1, self.repository.get_max_server_revision(submission_id) + 1),
                client_saved_at=datetime.now(timezone.utc),
                device_id=None,
                station_id=None,
                metadata_json={"source": "answer_file_upload", **safe_metadata},
            )
            self.repository.attach_answer_state_to_file_asset(
                answer_file_asset_id=int(asset["answer_file_asset_id"]),
                answer_state_id=int(answer_state["answer_state_id"]),
            )
            self.repository.update_submission_after_autosave(submission_id=submission_id)
            asset["answer_state_id"] = int(answer_state["answer_state_id"])
            return self._answer_file_response_payload(asset)
        except ApiError:
            if storage_path.exists():
                storage_path.unlink(missing_ok=True)
            raise
        except Exception as exc:
            if storage_path.exists():
                storage_path.unlink(missing_ok=True)
            raise ApiError(
                status_code=500,
                code="FILE_STORAGE_ERROR",
                message="Failed to store uploaded answer file",
                details={"generated_exam_question_id": int(generated_exam_question_id)},
            ) from exc
        finally:
            await upload_file.close()

    def get_answer_file_metadata(
        self,
        *,
        submission_id: int,
        generated_exam_question_id: int,
        current_user: dict,
    ) -> dict:
        _ = self.assert_submission_access(submission_id=submission_id, current_user=current_user)
        question = self.repository.get_submission_question_detail(
            submission_id=submission_id,
            generated_exam_question_id=generated_exam_question_id,
        )
        if question is None:
            raise ApiError(
                status_code=404,
                code="QUESTION_NOT_FOUND",
                message="Question is not found in submission",
                details={"generated_exam_question_id": int(generated_exam_question_id)},
            )

        asset = self.repository.get_current_answer_file_asset(
            submission_id=submission_id,
            generated_exam_question_id=generated_exam_question_id,
        )
        if asset is None:
            raise ApiError(
                status_code=404,
                code="QUESTION_NOT_FOUND",
                message="No uploaded file is found for this question",
                details={"generated_exam_question_id": int(generated_exam_question_id)},
            )
        return self._answer_file_response_payload(asset)

    def get_answer_file_content(
        self,
        *,
        submission_id: int,
        generated_exam_question_id: int,
        current_user: dict,
    ) -> dict:
        _ = self.assert_submission_access(submission_id=submission_id, current_user=current_user)
        question = self.repository.get_submission_question_detail(
            submission_id=submission_id,
            generated_exam_question_id=generated_exam_question_id,
        )
        if question is None:
            raise ApiError(
                status_code=404,
                code="QUESTION_NOT_FOUND",
                message="Question is not found in submission",
                details={"generated_exam_question_id": int(generated_exam_question_id)},
            )

        asset = self.repository.get_current_answer_file_asset(
            submission_id=submission_id,
            generated_exam_question_id=generated_exam_question_id,
        )
        if asset is None:
            raise ApiError(
                status_code=404,
                code="QUESTION_NOT_FOUND",
                message="No uploaded file is found for this question",
                details={"generated_exam_question_id": int(generated_exam_question_id)},
            )
        path = resolve_answer_storage_path(str(asset["internal_storage_key"]))
        if not path.exists() or not path.is_file():
            raise ApiError(
                status_code=500,
                code="FILE_STORAGE_ERROR",
                message="Stored answer file is not available",
                details={"generated_exam_question_id": int(generated_exam_question_id)},
            )
        return {
            "content_path": str(path),
            "mime_type": str(asset["mime_type"]),
            "original_filename": str(asset["original_filename"]),
        }

    def supersede_answer_file(
        self,
        *,
        submission_id: int,
        generated_exam_question_id: int,
        current_user: dict,
    ) -> dict:
        submission = self.assert_submission_access(submission_id=submission_id, current_user=current_user)
        if "STUDENT" in self._roles(current_user):
            submission_context = self._load_runtime_policy_context(submission=submission)
            self._assert_student_submit_eligible(submission_context=submission_context)
        self._assert_submission_not_sealed(submission_id)
        question = self.repository.get_submission_question_detail(
            submission_id=submission_id,
            generated_exam_question_id=generated_exam_question_id,
        )
        if question is None:
            raise ApiError(
                status_code=404,
                code="QUESTION_NOT_FOUND",
                message="Question is not found in submission",
                details={"generated_exam_question_id": int(generated_exam_question_id)},
            )
        actor_user_id = int(current_user["user_id"]) if current_user.get("user_id") is not None else None
        affected = self.repository.supersede_active_answer_file_assets(
            submission_id=submission_id,
            generated_exam_question_id=generated_exam_question_id,
            superseded_by=actor_user_id,
        )
        if affected <= 0:
            raise ApiError(
                status_code=404,
                code="QUESTION_NOT_FOUND",
                message="No active uploaded file is found for this question",
                details={"generated_exam_question_id": int(generated_exam_question_id)},
            )
        self.repository.upsert_answer_state(
            submission_id=submission_id,
            generated_exam_question_id=generated_exam_question_id,
            answer_type="FILE_REF",
            answer_text=None,
            answer_payload_json={"status": "SUPERSEDED", "file_asset_id": None},
            answer_hash=None,
            answer_length=None,
            client_version=max(1, self.repository.get_max_server_revision(submission_id) + 1),
            client_saved_at=datetime.now(timezone.utc),
            device_id=None,
            station_id=None,
            metadata_json={"source": "answer_file_supersede"},
        )
        self.repository.update_submission_after_autosave(submission_id=submission_id)
        return {
            "submission_id": int(submission_id),
            "generated_exam_question_id": int(generated_exam_question_id),
            "status": "SUPERSEDED",
        }

    def seal_submission(self, *, submission_id: int, payload: dict, current_user: dict) -> dict:
        submission = self.assert_submission_access(submission_id=submission_id, current_user=current_user)

        requested_seal_reason = str(payload.get("seal_reason") or "").strip().upper()
        seal_reason = normalize_seal_reason(requested_seal_reason)
        if seal_reason not in ALLOWED_SEAL_REASONS:
            raise ApiError(
                status_code=400,
                code="invalid_seal_reason",
                message="Unsupported seal reason",
                details={
                    "seal_reason": requested_seal_reason,
                    "normalized_seal_reason": seal_reason,
                },
            )

        seal_idempotency_key = str(payload.get("seal_idempotency_key") or "").strip()
        if not seal_idempotency_key:
            raise ApiError(
                status_code=400,
                code="invalid_seal_idempotency_key",
                message="seal_idempotency_key is required",
                details={},
            )

        roles = self._roles(current_user)
        if "STUDENT" in roles and seal_reason not in _STUDENT_ALLOWED_SEAL_REASONS:
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Student cannot use non-submit seal reasons",
                details={"seal_reason": seal_reason},
            )

        if seal_reason in FORCE_SEAL_REASONS and not roles.intersection({"ADMIN", "ACADEMIC_OFFICER", "INSTRUCTOR", "PROCTOR"}):
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Force seal requires proctor/admin roles",
                details={"seal_reason": seal_reason},
            )

        if seal_reason in {"TIME_EXPIRED", "SYSTEM_RECOVERY_SEAL"} and "STUDENT" in roles:
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Student cannot use internal seal reasons",
                details={"seal_reason": seal_reason},
            )

        sanitized_context = self._sanitize_submission_context(payload.get("metadata_json"))
        note = self._normalize_note(payload.get("note"))

        with self._transaction_scope():
            locked_submission = self._lock_submission_runtime_context(int(submission_id))
            existing_seal = self.repository.get_seal_by_submission_id(submission_id)
            if existing_seal is not None:
                existing_status = str(existing_seal["seal_status"]).upper()
                if existing_status != "SEALED":
                    raise ApiError(
                        status_code=409,
                        code="submission_seal_already_exists",
                        message="Submission already has a non-active seal row",
                        details={
                            "exam_submission_id": submission_id,
                            "submission_seal_id": int(existing_seal["submission_seal_id"]),
                            "seal_status": existing_status,
                        },
                    )
                summary = self.repository.get_seal_summary(submission_id)
                if summary is None:
                    raise ApiError(
                        status_code=500,
                        code="seal_summary_missing",
                        message="Seal summary is missing",
                        details={"exam_submission_id": submission_id},
                    )
                summary_payload = map_seal_summary_row(summary)
                return self._seal_contract_response(idempotent=True, summary_payload=summary_payload)

            preflight = self._evaluate_seal_preflight(
                submission_id=int(submission_id),
                submission_context=locked_submission,
            )
            self._raise_for_preflight_blockers(submission_id=int(submission_id), preflight=preflight)

            answer_count = self.repository.get_answer_state_count(submission_id)
            new_submission_status = status_for_seal_reason(seal_reason)
            seal = self.repository.create_submission_seal(
                submission_id=submission_id,
                seal_idempotency_key=seal_idempotency_key,
                seal_status="SEALED",
                seal_reason=seal_reason,
                sealed_by=int(current_user["user_id"]),
                answer_count=answer_count,
                submission_hash=None,
                metadata_json=sanitized_context,
            )

            sealed_answer_count = self.repository.create_sealed_answers_from_state(
                submission_id=submission_id,
                submission_seal_id=int(seal["submission_seal_id"]),
            )
            if int(sealed_answer_count) != int(answer_count):
                raise ApiError(
                    status_code=409,
                    code="sealed_answer_snapshot_mismatch",
                    message="Sealed answer snapshot count does not match answer_state count",
                    details={
                        "exam_submission_id": submission_id,
                        "submission_seal_id": int(seal["submission_seal_id"]),
                        "answer_state_count": int(answer_count),
                        "sealed_answer_count": int(sealed_answer_count),
                    },
                )

            self.repository.mark_sealed_file_assets(
                submission_id=submission_id,
                submission_seal_id=int(seal["submission_seal_id"]),
            )

            self.repository.update_submission_after_seal(
                submission_id=submission_id,
                submission_status=new_submission_status,
                seal_reason=seal_reason,
            )
            self._record_submission_history(
                submission_id=int(submission_id),
                exam_session_id=(int(locked_submission["exam_session_id"]) if locked_submission.get("exam_session_id") is not None else None),
                current_user=current_user,
                from_status=(str(locked_submission.get("submission_status") or "").strip().upper() or None),
                to_status=new_submission_status,
                seal_reason=seal_reason,
                note=note,
                idempotency_key=seal_idempotency_key,
                context_json=sanitized_context,
            )

            summary = self.repository.get_seal_summary(submission_id)
            if summary is None:
                raise ApiError(
                    status_code=500,
                    code="seal_summary_missing",
                    message="Seal summary is missing",
                    details={"exam_submission_id": submission_id},
                )

            summary_payload = map_seal_summary_row(summary)
            return self._seal_contract_response(idempotent=False, summary_payload=summary_payload)

    def get_seal_status(self, *, submission_id: int, current_user: dict) -> dict:
        self.assert_submission_access(submission_id=submission_id, current_user=current_user)

        summary = self.repository.get_seal_summary(submission_id)
        if summary is None:
            raise ApiError(
                status_code=404,
                code="submission_not_sealed",
                message="Submission is not sealed",
                details={"exam_submission_id": submission_id},
            )
        summary_payload = map_seal_summary_row(summary)
        return self._seal_contract_response(idempotent=False, summary_payload=summary_payload)


def build_submission_service() -> SubmissionService:
    return SubmissionService()
