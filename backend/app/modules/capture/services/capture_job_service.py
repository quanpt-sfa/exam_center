"""Service layer for queue-only capture job orchestration."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from uuid import uuid4

from app.core.errors import ApiError
from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.capture.mappers.capture_mapper import (
    map_capture_artifact_row,
    map_capture_dataset_row,
    map_capture_job_status_row,
    map_capture_source_summary,
)
from app.modules.capture.repositories.capture_artifact_repository import CaptureArtifactRepository
from app.modules.capture.repositories.capture_dataset_repository import CaptureDatasetRepository
from app.modules.capture.repositories.capture_job_repository import CaptureJobRepository
from app.modules.capture.services.capture_event_logger import CaptureEventLogger
from app.modules.capture.services.capture_readiness_resolver import CaptureReadinessResolver


_RESOURCE_TYPE_TO_CAPTURE_TYPE = {
    "SQLSERVER_STUDENT_DB": "STUDENT_DATABASE_SNAPSHOT",
    "POSTGRES_STUDENT_DB": "STUDENT_DATABASE_SNAPSHOT",
    "MISA_DATABASE": "MISA_DATABASE_SNAPSHOT",
    "AMIS_TENANT": "AMIS_API_RAW_PULL",
    "FILE_WORKSPACE": "FILE_ARTIFACT",
    "LOCAL_AGENT_WORKSPACE": "FILE_ARTIFACT",
    "OTHER": "OTHER",
}

_PROFILE_SOURCE_TYPE_TO_CAPTURE_TYPE = {
    "SQLSERVER_DATABASE": "STUDENT_DATABASE_SNAPSHOT",
    "POSTGRES_DATABASE": "STUDENT_DATABASE_SNAPSHOT",
    "MISA_DATABASE": "MISA_DATABASE_SNAPSHOT",
    "AMIS_API": "AMIS_API_RAW_PULL",
    "FILE_UPLOAD": "FILE_ARTIFACT",
    "CUSTOM_API": "OTHER",
    "OTHER": "OTHER",
}


class CaptureJobService:
    """Business orchestration for capture API skeleton endpoints."""

    def __init__(
        self,
        *,
        capture_job_repository: CaptureJobRepository | None = None,
        capture_dataset_repository: CaptureDatasetRepository | None = None,
        capture_artifact_repository: CaptureArtifactRepository | None = None,
        readiness_resolver: CaptureReadinessResolver | None = None,
        event_logger: CaptureEventLogger | None = None,
        transaction_scope: Callable[[], AbstractContextManager[object]] | None = None,
    ) -> None:
        self.capture_job_repository = capture_job_repository or CaptureJobRepository()
        self.capture_dataset_repository = capture_dataset_repository or CaptureDatasetRepository()
        self.capture_artifact_repository = capture_artifact_repository or CaptureArtifactRepository()
        self.readiness_resolver = readiness_resolver or CaptureReadinessResolver()
        self.event_logger = event_logger or CaptureEventLogger(self.capture_job_repository)
        has_custom_dependencies = any(
            dep is not None
            for dep in (
                capture_job_repository,
                capture_dataset_repository,
                capture_artifact_repository,
                readiness_resolver,
                event_logger,
            )
        )
        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif has_custom_dependencies:
            self._transaction_scope = nullcontext
        else:
            self._transaction_scope = database_unit_of_work

    @staticmethod
    def _roles(current_user: dict) -> set[str]:
        return {str(role).upper() for role in current_user.get("roles", [])}

    def _assert_submission_access(self, submission_context: dict, current_user: dict) -> None:
        roles = self._roles(current_user)
        if "STUDENT" not in roles:
            return

        actor_user_id = int(current_user["user_id"])
        actor_student_id = self.capture_job_repository.get_student_id_by_user_id(actor_user_id)
        if actor_student_id is None or actor_student_id != int(submission_context["student_id"]):
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Student cannot access another student's capture resources",
                details={"exam_submission_id": int(submission_context["exam_submission_id"])},
            )

    def _resolve_submission_context(self, payload: dict) -> dict:
        exam_submission_id = payload.get("exam_submission_id")
        submission_seal_id = payload.get("submission_seal_id")

        if exam_submission_id is not None:
            row = self.capture_job_repository.get_submission_context_by_submission_id(int(exam_submission_id))
        elif submission_seal_id is not None:
            row = self.capture_job_repository.get_submission_context_by_seal_id(int(submission_seal_id))
        else:
            raise ApiError(
                status_code=400,
                code="invalid_capture_job_target",
                message="exam_submission_id or submission_seal_id is required",
                details={},
            )

        if row is None:
            raise ApiError(
                status_code=404,
                code="submission_not_found",
                message="Submission target not found",
                details={
                    "exam_submission_id": exam_submission_id,
                    "submission_seal_id": submission_seal_id,
                },
            )
        return row

    def _resolve_capture_source(self, submission_context: dict) -> dict:
        binding = self.capture_job_repository.get_resource_binding_source(
            exam_session_id=int(submission_context["exam_session_id"]),
            student_id=int(submission_context["student_id"]),
            generated_exam_instance_id=(
                int(submission_context["generated_exam_instance_id"])
                if submission_context.get("generated_exam_instance_id") is not None
                else None
            ),
        )

        profile = None
        if binding is not None and binding.get("capture_profile_id") is not None:
            profile = self.capture_job_repository.get_capture_profile_summary_by_id(
                int(binding["capture_profile_id"])
            )
        if profile is None and binding is not None and binding.get("capture_profile_code"):
            profile = self.capture_job_repository.get_capture_profile_summary_by_code(
                str(binding["capture_profile_code"])
            )

        default_profile_hint = None
        exam_version_id = submission_context.get("exam_version_id")
        if profile is None and exam_version_id is not None:
            default_profile_hint = self.capture_job_repository.get_default_capture_profile_hint_by_exam_version(
                int(exam_version_id)
            )
            if default_profile_hint and default_profile_hint.get("default_capture_profile_code"):
                profile = self.capture_job_repository.get_capture_profile_summary_by_code(
                    str(default_profile_hint["default_capture_profile_code"])
                )

        self.readiness_resolver.ensure_capture_source_resolved(
            binding=binding,
            profile=profile,
            default_profile_hint=default_profile_hint,
        )

        return {
            "binding": binding,
            "profile": profile,
            "default_profile_hint": default_profile_hint,
        }

    @staticmethod
    def _build_source_summary(resolved_source: dict) -> dict:
        binding = resolved_source.get("binding")
        profile = resolved_source.get("profile")

        if binding is not None:
            return {
                "resolved_from": "resource_binding",
                "resource_binding_id": int(binding["resource_binding_id"]),
                "capture_profile_code": binding.get("capture_profile_code"),
                "resource_type": binding.get("resource_type"),
                "resource_location_mode": binding.get("resource_location_mode"),
            }

        if profile is not None:
            return {
                "resolved_from": "capture_profile",
                "capture_profile_id": int(profile["capture_profile_id"]),
                "capture_profile_code": profile.get("profile_code"),
                "resource_type": profile.get("source_type"),
                "resource_location_mode": profile.get("source_location_mode"),
            }

        return {
            "resolved_from": None,
            "capture_profile_code": None,
            "resource_type": None,
            "resource_location_mode": None,
        }

    def _infer_capture_type(self, *, requested_capture_type: str | None, resolved_source: dict) -> str:
        if requested_capture_type:
            return str(requested_capture_type).upper()

        binding = resolved_source.get("binding")
        if binding is not None and binding.get("resource_type"):
            resource_type = str(binding["resource_type"]).upper()
            return _RESOURCE_TYPE_TO_CAPTURE_TYPE.get(resource_type, "OTHER")

        profile = resolved_source.get("profile")
        if profile is not None and profile.get("source_type"):
            source_type = str(profile["source_type"]).upper()
            return _PROFILE_SOURCE_TYPE_TO_CAPTURE_TYPE.get(source_type, "OTHER")

        return "OTHER"

    @staticmethod
    def _merge_metadata(*, metadata_json: dict | None, source_summary: dict) -> dict:
        merged = dict(metadata_json or {})
        merged["source_resolution"] = {
            "resolved_from": source_summary.get("resolved_from"),
            "resource_binding_id": source_summary.get("resource_binding_id"),
            "capture_profile_id": source_summary.get("capture_profile_id"),
            "capture_profile_code": source_summary.get("capture_profile_code"),
            "resource_type": source_summary.get("resource_type"),
            "resource_location_mode": source_summary.get("resource_location_mode"),
        }
        return merged

    def _require_job_status_with_access(self, *, capture_job_id: int, current_user: dict) -> dict:
        status_row = self.capture_job_repository.get_job_status_view(capture_job_id)
        if status_row is None:
            raise ApiError(
                status_code=404,
                code="capture_job_not_found",
                message="Capture job not found",
                details={"capture_job_id": capture_job_id},
            )

        submission_context = self.capture_job_repository.get_submission_context_by_submission_id(
            int(status_row["exam_submission_id"])
        )
        if submission_context is not None:
            self._assert_submission_access(submission_context, current_user)

        return status_row

    def create_capture_job(self, *, payload: dict, current_user: dict) -> dict:
        with self._transaction_scope():
            submission_context = self._resolve_submission_context(payload)
            self._assert_submission_access(submission_context, current_user)
            self.readiness_resolver.ensure_submission_is_sealed(submission_context)

            resolved_source = self._resolve_capture_source(submission_context)
            source_summary = self._build_source_summary(resolved_source)
            capture_type = self._infer_capture_type(
                requested_capture_type=payload.get("capture_type"),
                resolved_source=resolved_source,
            )

            idempotency_key = str(payload.get("idempotency_key") or str(uuid4())).strip()
            existing = self.capture_job_repository.get_job_by_idempotency(
                exam_submission_id=int(submission_context["exam_submission_id"]),
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                status_row = self.capture_job_repository.get_job_status_view(int(existing["capture_job_id"]))
                if status_row is not None:
                    return {
                        "idempotent": True,
                        "job": map_capture_job_status_row(status_row),
                        "source": map_capture_source_summary(source_summary),
                    }
                raise ApiError(
                    status_code=409,
                    code="idempotent_capture_job_conflict",
                    message="Idempotent capture job already exists",
                    details={"capture_job_id": int(existing["capture_job_id"])},
                )

            existing_for_type = self.capture_job_repository.get_job_by_submission_and_type(
                exam_submission_id=int(submission_context["exam_submission_id"]),
                capture_type=capture_type,
            )
            if existing_for_type is not None:
                raise ApiError(
                    status_code=409,
                    code="capture_job_already_exists",
                    message="Capture job already exists for submission and capture_type",
                    details={
                        "capture_job_id": int(existing_for_type["capture_job_id"]),
                        "capture_type": capture_type,
                    },
                )

            exam_session_id = submission_context.get("exam_session_id")
            generated_exam_instance_id = submission_context.get("generated_exam_instance_id")
            if exam_session_id is None or generated_exam_instance_id is None:
                raise ApiError(
                    status_code=409,
                    code="capture_job_context_incomplete",
                    message="Submission context lacks required capture job fields",
                    details={
                        "exam_submission_id": int(submission_context["exam_submission_id"]),
                        "exam_session_id": exam_session_id,
                        "generated_exam_instance_id": generated_exam_instance_id,
                    },
                )

            metadata_json = self._merge_metadata(metadata_json=payload.get("metadata_json"), source_summary=source_summary)
            job = self.capture_job_repository.create_job(
                exam_submission_id=int(submission_context["exam_submission_id"]),
                submission_seal_id=int(submission_context["submission_seal_id"]),
                exam_session_id=int(exam_session_id),
                generated_exam_instance_id=int(generated_exam_instance_id),
                idempotency_key=idempotency_key,
                capture_type=capture_type,
                requested_by=int(current_user["user_id"]),
                metadata_json=metadata_json,
            )

            self.event_logger.log_queued(
                capture_job_id=int(job["capture_job_id"]),
                actor_user_id=int(current_user["user_id"]),
                payload={"source": "api_create", "idempotency_key": idempotency_key},
            )

            status_row = self.capture_job_repository.get_job_status_view(int(job["capture_job_id"]))
            if status_row is None:
                raise ApiError(
                    status_code=500,
                    code="capture_job_status_missing",
                    message="Failed to load created capture job status",
                    details={"capture_job_id": int(job["capture_job_id"])},
                )

            # Intentionally queue-only: actual capture execution belongs to worker runtime.
            return {
                "idempotent": False,
                "job": map_capture_job_status_row(status_row),
                "source": map_capture_source_summary(source_summary),
            }

    def get_capture_job_status(self, *, capture_job_id: int, current_user: dict) -> dict:
        status_row = self._require_job_status_with_access(capture_job_id=capture_job_id, current_user=current_user)
        return {"job": map_capture_job_status_row(status_row)}

    def list_capture_datasets(self, *, capture_job_id: int, current_user: dict) -> dict:
        self._require_job_status_with_access(capture_job_id=capture_job_id, current_user=current_user)
        rows = self.capture_dataset_repository.list_datasets_by_job_id(capture_job_id)
        return {
            "capture_job_id": capture_job_id,
            "items": [map_capture_dataset_row(row) for row in rows],
        }

    def list_capture_artifacts(self, *, capture_job_id: int, current_user: dict) -> dict:
        self._require_job_status_with_access(capture_job_id=capture_job_id, current_user=current_user)
        rows = self.capture_artifact_repository.list_artifacts_by_job_id(capture_job_id)
        return {
            "capture_job_id": capture_job_id,
            "items": [map_capture_artifact_row(row) for row in rows],
        }

    def retry_capture_job(self, *, capture_job_id: int, payload: dict, current_user: dict) -> dict:
        job = self.capture_job_repository.get_job_by_id(capture_job_id)
        if job is None:
            raise ApiError(
                status_code=404,
                code="capture_job_not_found",
                message="Capture job not found",
                details={"capture_job_id": capture_job_id},
            )

        submission_context = self.capture_job_repository.get_submission_context_by_submission_id(
            int(job["exam_submission_id"])
        )
        if submission_context is not None:
            self._assert_submission_access(submission_context, current_user)

        retry_reason = str(payload.get("reason") or "manual_retry").strip()
        metadata_update = dict(payload.get("metadata_json") or {})
        metadata_update.update(
            {
                "retry_reason": retry_reason,
                "retry_requested_by": int(current_user["user_id"]),
            }
        )
        updated = self.capture_job_repository.queue_retry(
            capture_job_id=capture_job_id,
            metadata_json=metadata_update,
        )
        if updated is None:
            raise ApiError(
                status_code=404,
                code="capture_job_not_found",
                message="Capture job not found",
                details={"capture_job_id": capture_job_id},
            )

        self.event_logger.log_retried(
            capture_job_id=capture_job_id,
            actor_user_id=int(current_user["user_id"]),
            payload={"source": "api_retry", "reason": retry_reason},
        )

        status_row = self.capture_job_repository.get_job_status_view(capture_job_id)
        if status_row is None:
            raise ApiError(
                status_code=500,
                code="capture_job_status_missing",
                message="Failed to load retried capture job status",
                details={"capture_job_id": capture_job_id},
            )

        return {"job": map_capture_job_status_row(status_row)}

    def _execute_capture_now(self, *, capture_job_id: int) -> None:
        """Worker-only placeholder. Never called from API request path."""
        raise NotImplementedError("Capture worker execution is out of scope")


def build_capture_job_service() -> CaptureJobService:
    return CaptureJobService()
