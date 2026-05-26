"""Service tests for MD-10.3 async import status and error projections."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone

import pytest

from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.services.import_status_service import ImportStatusService


class _FakeRepository:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.snapshot: dict | None = {
            "import_job_id": 12,
            "template_code": "STUDENT_V1",
            "job_status": "RUNNING",
            "validation_status": "PENDING",
            "commit_status": "NOT_COMMITTED",
            "attempt_count": 2,
            "max_attempts": 3,
            "claimed_by": "worker-abc-123",
            "claimed_at": now,
            "started_at": now,
            "finished_at": None,
            "last_error_code": "transient_error",
            "last_error_message": "permission denied token=abc123 password=secret postgres://user:pw@localhost/db",
            "created_at": now,
            "updated_at": now,
            "total_rows": 100,
            "valid_rows": 95,
            "invalid_rows": 5,
            "pending_rows": 0,
            "committed_rows": 40,
            "failed_rows": 2,
            "skipped_rows": 53,
        }
        self.job_exists = True
        self.error_rows = [
            {
                "row_number": 2,
                "field_name": "student_code",
                "error_code": "required",
                "error_message": "student_code is required token=abc",
                "severity": "error",
                "created_at": now,
            },
            {
                "row_number": 4,
                "field_name": "full_name",
                "error_code": "invalid_format",
                "error_message": "full_name has invalid format",
                "severity": "warning",
                "created_at": now,
            },
        ]

    def get_import_status_snapshot(self, *, import_job_id: int, conn=None):
        _ = (import_job_id, conn)
        return None if self.snapshot is None else dict(self.snapshot)

    def get_job_by_id(self, import_job_id: int, conn=None):
        _ = conn
        if not self.job_exists:
            return None
        return {"import_job_id": int(import_job_id)}

    def list_row_errors_paginated(self, *, import_job_id: int, offset: int, limit: int, conn=None):
        _ = (import_job_id, conn)
        items = self.error_rows[offset : offset + limit]
        return [dict(item) for item in items], len(self.error_rows)


class _FakePreviewService:
    def list_rows(self, *, import_job_id: int, pagination: dict | None, actor: dict):
        _ = (import_job_id, pagination, actor)
        return {
            "items": [
                {
                    "import_row_id": 10,
                    "row_number": 1,
                    "validation_status": "VALID",
                    "commit_status": "NOT_COMMITTED",
                    "raw_row": {
                        "student_code": "S001",
                        "password": "do-not-expose",
                        "nested": {"token": "abc", "safe": "ok"},
                    },
                    "normalized_row": {
                        "student_code": "S001",
                        "connection_string": "postgres://user:pw@localhost/db",
                    },
                    "errors": [
                        {
                            "row_number": 1,
                            "field": "student_code",
                            "code": "required",
                            "message": "token=abc missing",
                            "details": {"api_key": "hidden", "severity": "ERROR"},
                        }
                    ],
                }
            ],
            "pagination": {
                "page": 1,
                "page_size": 20,
                "total": 1,
                "total_pages": 1,
                "has_next": False,
                "has_previous": False,
            },
        }


def test_get_import_status_returns_404_for_missing_job() -> None:
    repository = _FakeRepository()
    repository.snapshot = None
    service = ImportStatusService(repository=repository, preview_service=_FakePreviewService())

    with pytest.raises(MasterDataNotFoundError):
        service.get_import_status(import_job_id=999, actor={"user_id": 1})


def test_get_import_status_returns_aggregates_and_sanitized_fields() -> None:
    service = ImportStatusService(repository=_FakeRepository(), preview_service=_FakePreviewService())

    result = service.get_import_status(import_job_id=12, actor={"user_id": 1})

    assert result["import_job_id"] == 12
    assert result["import_type"] == "STUDENTS"
    assert result["status"] == "RUNNING"
    assert result["worker_status"] == "RUNNING"
    assert result["total_rows"] == 100
    assert result["valid_rows"] == 95
    assert result["invalid_rows"] == 5
    assert result["committed_rows"] == 40
    assert result["failed_rows"] == 2
    assert result["claimed_by"] == "wo***"
    assert "abc123" not in str(result["last_error_message"])
    assert "secret" not in str(result["last_error_message"])
    assert "<redacted>" in str(result["last_error_message"])


def test_list_import_errors_is_paginated_and_sanitized() -> None:
    service = ImportStatusService(repository=_FakeRepository(), preview_service=_FakePreviewService())

    result = service.list_import_errors(
        import_job_id=12,
        pagination={"page": 2, "page_size": 1},
        actor={"user_id": 1},
    )

    assert result["pagination"]["page"] == 2
    assert result["pagination"]["page_size"] == 1
    assert result["pagination"]["total"] == 2
    assert len(result["items"]) == 1
    assert result["items"][0]["error_code"] == "invalid_format"


def test_list_import_rows_sanitizes_sensitive_payloads() -> None:
    service = ImportStatusService(repository=_FakeRepository(), preview_service=_FakePreviewService())

    result = service.list_import_rows(
        import_job_id=12,
        pagination={"page": 1, "page_size": 20},
        actor={"user_id": 1},
    )

    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["raw_row"]["password"] == "<redacted>"
    assert item["raw_row"]["nested"]["token"] == "<redacted>"
    assert item["normalized_row"]["connection_string"] == "<redacted>"
    assert item["has_errors"] is True
    assert item["error_count"] == 1
    assert "abc" not in item["errors"][0]["message"]
    assert item["errors"][0]["details"]["api_key"] == "<redacted>"
