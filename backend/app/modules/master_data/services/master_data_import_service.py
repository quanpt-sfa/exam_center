"""MD-7 import foundation orchestration service for master-data staging/preview/commit."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
import re

from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.repositories.import_foundation_repository import ImportFoundationRepository
from app.modules.master_data.services.import_commit_service import ImportCommitService
from app.modules.master_data.services.import_commit_service import build_import_commit_service
from app.modules.master_data.services.import_preview_service import ImportPreviewService
from app.modules.master_data.services.import_preview_service import build_import_preview_service
from app.modules.master_data.services.import_validation_service import ImportValidationService
from app.modules.master_data.services.import_validation_service import build_import_validation_service


class MasterDataImportService:
    """Coordinates MD-7 import jobs from staging to synchronous validation and commit."""

    MAX_SYNC_VALIDATION_ROWS = 500

    def __init__(
        self,
        *,
        repository: ImportFoundationRepository | None = None,
        validation_service: ImportValidationService | None = None,
        preview_service: ImportPreviewService | None = None,
        commit_service: ImportCommitService | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._repository = repository or ImportFoundationRepository()
        self._validation_service = validation_service or build_import_validation_service()
        self._preview_service = preview_service or build_import_preview_service()
        self._commit_service = commit_service or build_import_commit_service()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif any(dep is not None for dep in (repository, validation_service, preview_service, commit_service)):
            self._transaction_scope = self._null_transaction_scope
        else:
            self._transaction_scope = database_unit_of_work

        self._template_to_import_type = {
            template_code: import_type
            for import_type, (template_code, _name, _entity) in self._repository.TEMPLATE_MAP.items()
        }

    @staticmethod
    @contextmanager
    def _null_transaction_scope():
        yield None

    @staticmethod
    def _actor_user_id(actor: dict) -> int | None:
        value = actor.get("user_id")
        return int(value) if value is not None else None

    @staticmethod
    def _actor_agent(actor: dict) -> str | None:
        username = str(actor.get("username") or "").strip()
        if username:
            return username
        email = str(actor.get("email") or "").strip()
        return email or None

    @staticmethod
    def _sanitize_error_message(message: str) -> str:
        redacted = re.sub(r"(?i)(password|secret|token)\s*[:=]\s*[^,\s]+", r"\1=<redacted>", message)
        redacted = re.sub(r"(?i)(authorization)\s*[:=]\s*[^,\s]+", r"\1=<redacted>", redacted)
        return redacted

    @staticmethod
    def _contains_replacement_character(value: object) -> bool:
        if isinstance(value, str):
            return "\uFFFD" in value
        if isinstance(value, dict):
            return any(MasterDataImportService._contains_replacement_character(item) for item in value.values())
        if isinstance(value, list):
            return any(MasterDataImportService._contains_replacement_character(item) for item in value)
        return False

    @staticmethod
    def _execute_sql(conn: object | None, sql: str) -> None:
        if conn is None:
            return
        if not hasattr(conn, "cursor"):
            return
        with conn.cursor() as cur:
            cur.execute(sql)

    def _derive_status(self, *, job: dict, latest_md7_status: str | None) -> str:
        if latest_md7_status:
            return latest_md7_status

        job_status = str(job.get("job_status") or "").strip().upper()
        validation_status = str(job.get("validation_status") or "").strip().upper()
        commit_status = str(job.get("commit_status") or "").strip().upper()

        if job_status == "COMMITTED" and commit_status == "COMMITTED":
            return "COMMITTED"
        if job_status == "VALIDATED" and validation_status == "PASSED":
            return "VALIDATED"
        if job_status == "FAILED" and commit_status == "NOT_COMMITTED":
            return "COMMIT_FAILED" if validation_status == "PASSED" else "VALIDATION_FAILED"
        if job_status == "ROLLED_BACK":
            return "CANCELLED"
        return "CREATED"

    def _build_job_response(self, *, job: dict, conn: object | None = None) -> dict:
        latest_status = self._repository.get_latest_md7_status(import_job_id=int(job["import_job_id"]), conn=conn)
        import_type = self._template_to_import_type.get(str(job.get("template_code") or "").strip().upper(), "STUDENTS")
        counts = self._repository.get_row_status_counts(import_job_id=int(job["import_job_id"]), conn=conn)

        return {
            "import_job_id": int(job["import_job_id"]),
            "import_type": import_type,
            "status": self._derive_status(job=job, latest_md7_status=latest_status),
            "validation_status": str(job.get("validation_status") or "").strip().upper(),
            "commit_status": str(job.get("commit_status") or "").strip().upper(),
            "counts": counts,
        }

    def create_import_job(self, *, command: dict, actor: dict) -> dict:
        import_type = str(command.get("import_type") or "").strip().upper()
        if import_type not in self._repository.TEMPLATE_MAP:
            raise MasterDataValidationError(
                "Unsupported import_type",
                details={
                    "import_type": import_type,
                    "supported_import_types": sorted(self._repository.TEMPLATE_MAP.keys()),
                },
            )

        rows = command.get("rows") or []
        if not isinstance(rows, list):
            raise MasterDataValidationError("rows must be a list")

        actor_user_id = self._actor_user_id(actor)
        actor_agent = self._actor_agent(actor)

        with self._transaction_scope() as conn:
            template = self._repository.ensure_template_for_import_type(import_type=import_type, conn=conn)
            job = self._repository.create_job(
                import_template_id=int(template["import_template_id"]),
                template_code=str(template["template_code"]),
                actor_user_id=actor_user_id,
                actor_agent=actor_agent,
                conn=conn,
            )

            for index, raw_row in enumerate(rows, start=1):
                if not isinstance(raw_row, dict):
                    raise MasterDataValidationError(
                        "Each staged row must be an object",
                        details={"row_number": index},
                    )
                if self._contains_replacement_character(raw_row):
                    raise MasterDataValidationError(
                        "File CSV có lỗi mã hóa tiếng Việt. Vui lòng tải lại file mẫu .xlsx hoặc lưu CSV dưới dạng CSV UTF-8.",
                        details={"row_number": index, "code": "invalid_text_encoding"},
                    )
                self._repository.insert_staging_row(
                    import_job_id=int(job["import_job_id"]),
                    row_number=index,
                    raw_row_json=raw_row,
                    conn=conn,
                )

            self._repository.record_md7_status(
                import_job_id=int(job["import_job_id"]),
                status="CREATED",
                actor_user_id=actor_user_id,
                actor_agent=actor_agent,
                details={"import_type": import_type, "staged_row_count": len(rows)},
                conn=conn,
            )

            self._repository.add_audit_event(
                import_job_id=int(job["import_job_id"]),
                event_type="IMPORT_JOB_CREATED",
                event_payload_json={
                    "import_type": import_type,
                    "source_filename": command.get("source_filename"),
                    "staged_row_count": len(rows),
                },
                actor_user_id=actor_user_id,
                actor_agent=actor_agent,
                conn=conn,
            )

            self._repository.add_audit_event(
                import_job_id=int(job["import_job_id"]),
                event_type="MD8_REQUEST",
                event_payload_json={"operation": "VALIDATE", "auto_commit": True},
                actor_user_id=actor_user_id,
                actor_agent=actor_agent,
                conn=conn,
            )
            self._repository.update_job_state(
                import_job_id=int(job["import_job_id"]),
                job_status="QUEUED",
                validation_status="PENDING",
                commit_status="NOT_COMMITTED",
                conn=conn,
            )
            self._repository.record_md7_status(
                import_job_id=int(job["import_job_id"]),
                status="QUEUED",
                actor_user_id=actor_user_id,
                actor_agent=actor_agent,
                details={"operation": "VALIDATE", "auto_commit": True},
                conn=conn,
            )
            queued_job = self._repository.get_job_by_id(int(job["import_job_id"]), conn=conn) or job
            return self._build_job_response(job=queued_job, conn=conn)

    def get_import_job(self, *, import_job_id: int, actor: dict) -> dict:
        _ = actor
        job = self._repository.get_job_by_id(int(import_job_id))
        if job is None:
            raise MasterDataNotFoundError(
                "Import job not found",
                details={"import_job_id": int(import_job_id)},
            )
        return self._build_job_response(job=job)

    def list_import_rows(self, *, import_job_id: int, pagination: dict | None, actor: dict) -> dict:
        return self._preview_service.list_rows(import_job_id=int(import_job_id), pagination=pagination, actor=actor)

    def validate_import_job(self, *, import_job_id: int, actor: dict) -> dict:
        actor_user_id = self._actor_user_id(actor)
        actor_agent = self._actor_agent(actor)

        with self._transaction_scope() as conn:
            job = self._repository.get_job_by_id(int(import_job_id), conn=conn)
            if job is None:
                raise MasterDataNotFoundError(
                    "Import job not found",
                    details={"import_job_id": int(import_job_id)},
                )

            import_type = self._template_to_import_type.get(str(job.get("template_code") or "").strip().upper())
            if not import_type:
                raise MasterDataValidationError(
                    "Unable to resolve import_type for this job",
                    details={"template_code": job.get("template_code")},
                )

            rows = self._repository.list_all_staging_rows(import_job_id=int(import_job_id), conn=conn)
            if not rows:
                raise MasterDataValidationError(
                    "No staged rows found for this import job",
                    details={"import_job_id": int(import_job_id)},
                )

            if len(rows) > self.MAX_SYNC_VALIDATION_ROWS:
                self._repository.update_job_state(
                    import_job_id=int(import_job_id),
                    job_status="FAILED",
                    validation_status="FAILED",
                    conn=conn,
                )
                self._repository.record_md7_status(
                    import_job_id=int(import_job_id),
                    status="VALIDATION_FAILED",
                    actor_user_id=actor_user_id,
                    actor_agent=actor_agent,
                    details={
                        "required_action": "NEEDS_WORKER",
                        "row_count": len(rows),
                        "max_sync_validation_rows": self.MAX_SYNC_VALIDATION_ROWS,
                    },
                    conn=conn,
                )
                raise MasterDataValidationError(
                    "Synchronous validation limit exceeded; worker is required",
                    details={
                        "required_action": "NEEDS_WORKER",
                        "row_count": len(rows),
                        "max_sync_validation_rows": self.MAX_SYNC_VALIDATION_ROWS,
                    },
                )

            self._repository.update_job_state(
                import_job_id=int(import_job_id),
                job_status="PARSED",
                validation_status="PENDING",
                conn=conn,
            )
            self._repository.record_md7_status(
                import_job_id=int(import_job_id),
                status="VALIDATING",
                actor_user_id=actor_user_id,
                actor_agent=actor_agent,
                details={"row_count": len(rows)},
                conn=conn,
            )

            self._repository.clear_row_errors(import_job_id=int(import_job_id), conn=conn)
            self._repository.reset_rows_for_revalidation(import_job_id=int(import_job_id), conn=conn)

            for row in rows:
                row_id = int(row["import_row_staging_id"])
                row_number = int(row["row_number"])
                normalized, errors = self._validation_service.validate_row(
                    import_type=import_type,
                    raw_row=dict(row.get("raw_row_json") or {}),
                )

                if errors:
                    self._repository.update_row_validation(
                        import_row_id=row_id,
                        validation_status="INVALID",
                        normalized_row_json=None,
                        conn=conn,
                    )
                    for item in errors:
                        field = item.get("field")
                        details = {"row_number": row_number}
                        if field is not None:
                            details["field"] = field
                        self._repository.add_row_error(
                            import_job_id=int(import_job_id),
                            import_row_id=row_id,
                            error_code=str(item.get("code") or "validation_error"),
                            error_message=str(item.get("message") or "Validation error"),
                            error_details=details,
                            conn=conn,
                        )
                    continue

                self._repository.update_row_validation(
                    import_row_id=row_id,
                    validation_status="VALID",
                    normalized_row_json=normalized,
                    conn=conn,
                )

            counts = self._repository.get_row_status_counts(import_job_id=int(import_job_id), conn=conn)
            invalid_rows = int(counts.get("invalid_rows") or 0)
            valid_rows = int(counts.get("valid_rows") or 0)

            if invalid_rows == 0 and valid_rows > 0:
                self._repository.update_job_state(
                    import_job_id=int(import_job_id),
                    job_status="VALIDATED",
                    validation_status="PASSED",
                    conn=conn,
                )
                self._repository.record_md7_status(
                    import_job_id=int(import_job_id),
                    status="VALIDATED",
                    actor_user_id=actor_user_id,
                    actor_agent=actor_agent,
                    details=counts,
                    conn=conn,
                )
            else:
                self._repository.update_job_state(
                    import_job_id=int(import_job_id),
                    job_status="FAILED",
                    validation_status="FAILED",
                    conn=conn,
                )
                self._repository.record_md7_status(
                    import_job_id=int(import_job_id),
                    status="VALIDATION_FAILED",
                    actor_user_id=actor_user_id,
                    actor_agent=actor_agent,
                    details=counts,
                    conn=conn,
                )

            updated_job = self._repository.get_job_by_id(int(import_job_id), conn=conn)
            if updated_job is None:
                raise MasterDataNotFoundError(
                    "Import job not found",
                    details={"import_job_id": int(import_job_id)},
                )
            return self._build_job_response(job=updated_job, conn=conn)

    def commit_import_job(self, *, import_job_id: int, command: dict, actor: dict) -> dict:
        actor_user_id = self._actor_user_id(actor)
        actor_agent = self._actor_agent(actor)

        with self._transaction_scope() as conn:
            job = self._repository.get_job_by_id(int(import_job_id), conn=conn)
            if job is None:
                raise MasterDataNotFoundError(
                    "Import job not found",
                    details={"import_job_id": int(import_job_id)},
                )

            validation_status = str(job.get("validation_status") or "").strip().upper()
            if validation_status != "PASSED":
                raise MasterDataValidationError(
                    "Only fully validated import jobs can be committed",
                    details={
                        "import_job_id": int(import_job_id),
                        "validation_status": validation_status,
                    },
                )

            import_type = self._template_to_import_type.get(str(job.get("template_code") or "").strip().upper())
            if not import_type:
                raise MasterDataValidationError(
                    "Unable to resolve import_type for this job",
                    details={"template_code": job.get("template_code")},
                )

            self._repository.record_md7_status(
                import_job_id=int(import_job_id),
                status="COMMITTING",
                actor_user_id=actor_user_id,
                actor_agent=actor_agent,
                details={"idempotency_key": command.get("idempotency_key")},
                conn=conn,
            )

            valid_rows = self._repository.list_valid_rows(import_job_id=int(import_job_id), conn=conn)
            if not valid_rows:
                raise MasterDataValidationError(
                    "No valid rows available to commit",
                    details={"import_job_id": int(import_job_id)},
                )

            committed_rows = 0
            failed_rows = 0

            for row in valid_rows:
                row_id = int(row["import_row_staging_id"])
                row_number = int(row["row_number"])
                normalized_row = dict(row.get("normalized_row_json") or {})
                savepoint_name = f"md7_commit_row_{row_id}"
                savepoint_started = False

                try:
                    self._execute_sql(conn, f"SAVEPOINT {savepoint_name}")
                    savepoint_started = True
                    self._commit_service.commit_row(
                        import_type=import_type,
                        normalized_row=normalized_row,
                        actor=actor,
                    )
                    self._execute_sql(conn, f"RELEASE SAVEPOINT {savepoint_name}")
                    self._repository.update_row_commit_status(
                        import_row_id=row_id,
                        commit_status="COMMITTED",
                        conn=conn,
                    )
                    committed_rows += 1
                except Exception as exc:  # noqa: BLE001
                    if savepoint_started:
                        try:
                            self._execute_sql(conn, f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                        finally:
                            self._execute_sql(conn, f"RELEASE SAVEPOINT {savepoint_name}")
                    failed_rows += 1
                    self._repository.update_row_commit_status(
                        import_row_id=row_id,
                        commit_status="FAILED",
                        conn=conn,
                    )

                    code = getattr(exc, "code", "commit_error")
                    raw_message = str(getattr(exc, "message", str(exc)) or "Commit failed")
                    message = self._sanitize_error_message(raw_message)
                    details = {"row_number": row_number, "phase": "commit"}
                    if hasattr(exc, "details") and isinstance(getattr(exc, "details"), dict):
                        details.update(getattr(exc, "details"))

                    self._repository.add_row_error(
                        import_job_id=int(import_job_id),
                        import_row_id=row_id,
                        error_code=str(code),
                        error_message=message,
                        error_details=details,
                        conn=conn,
                    )

            total_rows = len(valid_rows)
            summary = {
                "import_type": import_type,
                "committed_rows": committed_rows,
                "failed_rows": failed_rows,
                "total_rows": total_rows,
                "idempotency_key": command.get("idempotency_key"),
            }

            if failed_rows == 0:
                self._repository.update_job_state(
                    import_job_id=int(import_job_id),
                    job_status="COMMITTED",
                    commit_status="COMMITTED",
                    conn=conn,
                )
                self._repository.create_commit_record(
                    import_job_id=int(import_job_id),
                    commit_status="COMMITTED",
                    committed_by=actor_user_id,
                    summary_json=summary,
                    conn=conn,
                )
                self._repository.record_md7_status(
                    import_job_id=int(import_job_id),
                    status="COMMITTED",
                    actor_user_id=actor_user_id,
                    actor_agent=actor_agent,
                    details=summary,
                    conn=conn,
                )
                status = "COMMITTED"
            else:
                self._repository.update_job_state(
                    import_job_id=int(import_job_id),
                    job_status="FAILED",
                    commit_status="NOT_COMMITTED",
                    conn=conn,
                )
                self._repository.create_commit_record(
                    import_job_id=int(import_job_id),
                    commit_status="FAILED",
                    committed_by=actor_user_id,
                    summary_json=summary,
                    conn=conn,
                )
                self._repository.record_md7_status(
                    import_job_id=int(import_job_id),
                    status="COMMIT_FAILED",
                    actor_user_id=actor_user_id,
                    actor_agent=actor_agent,
                    details=summary,
                    conn=conn,
                )
                status = "COMMIT_FAILED"

            return {
                "import_job_id": int(import_job_id),
                "status": status,
                "committed_rows": committed_rows,
                "failed_rows": failed_rows,
                "total_rows": total_rows,
            }


def build_master_data_import_service() -> MasterDataImportService:
    """FastAPI dependency factory for master-data import service."""

    return MasterDataImportService()
