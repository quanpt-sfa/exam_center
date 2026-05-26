"""Endpoint tests for import API staging and commit workflows."""

from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient

from app.main import app
from app.core.permissions import PermissionDeniedError
from app.modules.importing.permissions import require_imports_commit, require_imports_read, require_imports_write
from app.modules.importing.services.import_service import build_import_service


class FakeImportService:
    def __init__(self) -> None:
        self.next_job_id = 1
        self.jobs: dict[int, dict] = {}
        self.files: dict[int, bytes] = {}
        self.rows: dict[int, list[dict]] = {}
        self.errors: dict[int, list[dict]] = {}
        self.last_create_payload: dict | None = None
        self.last_commit_payload: dict | None = None

    def list_templates(self) -> dict:
        return {"templates": [{"template_code": "STUDENT_V1"}, {"template_code": "ENROLLMENT_V1"}]}

    def get_template(self, template_code: str) -> dict:
        if template_code == "STUDENT_V1":
            return {
                "template": {
                    "template_code": "STUDENT_V1",
                    "template_name": "Student Import Template V1",
                    "schema_version": "V1",
                    "entity_code": "STUDENT",
                }
            }
        if template_code == "ENROLLMENT_V1":
            return {
                "template": {
                    "template_code": "ENROLLMENT_V1",
                    "template_name": "Enrollment Import Template V1",
                    "schema_version": "V1",
                    "entity_code": "ENROLLMENT",
                }
            }
        raise RuntimeError("template not found")

    def create_job(self, payload: dict) -> dict:
        self.last_create_payload = dict(payload)
        job_id = self.next_job_id
        self.next_job_id += 1
        self.jobs[job_id] = {
            "import_job_id": job_id,
            "template_code": payload["template_code"],
            "job_status": "CREATED",
            "validation_status": "PENDING",
            "commit_status": "NOT_COMMITTED",
        }
        return self.jobs[job_id]

    def upload_job_file(self, *, job_id: int, filename: str, file_bytes: bytes) -> dict:
        self.files[job_id] = file_bytes
        self.jobs[job_id]["job_status"] = "UPLOADED"
        return {
            "import_job_id": job_id,
            "import_file_id": 1,
            "filename": filename,
            "file_size_bytes": len(file_bytes),
            "job_status": "UPLOADED",
        }

    def parse_job(self, job_id: int) -> dict:
        content = self.files[job_id].decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))
        parsed_rows = []
        for index, row in enumerate(reader, start=2):
            parsed_rows.append(
                {
                    "import_row_staging_id": index,
                    "row_number": index,
                    "raw_row": row,
                    "normalized_row": None,
                    "validation_status": "PENDING",
                    "commit_status": "NOT_COMMITTED",
                }
            )
        self.rows[job_id] = parsed_rows
        self.jobs[job_id]["job_status"] = "PARSED"
        return {
            "import_job_id": job_id,
            "import_file_id": 1,
            "import_sheet_id": 1,
            "sheet_name": "csv",
            "row_count": len(parsed_rows),
            "job_status": "PARSED",
        }

    def validate_job(self, job_id: int) -> dict:
        invalid = 0
        valid = 0
        self.errors[job_id] = []
        for row in self.rows[job_id]:
            student_code = str(row["raw_row"].get("student_code") or "").strip()
            full_name = str(row["raw_row"].get("full_name") or "").strip()
            if not student_code or not full_name:
                row["validation_status"] = "INVALID"
                invalid += 1
                self.errors[job_id].append(
                    {
                        "import_row_error_id": len(self.errors[job_id]) + 1,
                        "import_row_staging_id": row["import_row_staging_id"],
                        "error_code": "validation_error",
                        "error_message": "student_code and full_name are required",
                        "error_details": {"row_number": row["row_number"]},
                    }
                )
            else:
                row["validation_status"] = "VALID"
                row["normalized_row"] = {
                    "student_code": student_code,
                    "full_name": full_name,
                    "student_status": "ACTIVE",
                    "person_status": "ACTIVE",
                }
                valid += 1

        validation_status = "PASSED" if invalid == 0 else "FAILED"
        self.jobs[job_id]["job_status"] = "VALIDATED"
        self.jobs[job_id]["validation_status"] = validation_status
        return {
            "import_job_id": job_id,
            "template_code": self.jobs[job_id]["template_code"],
            "job_status": "VALIDATED",
            "validation_status": validation_status,
            "counts": {
                "total_rows": len(self.rows[job_id]),
                "valid_rows": valid,
                "invalid_rows": invalid,
            },
        }

    def preview_job(self, *, job_id: int, limit: int = 100, offset: int = 0) -> dict:
        items = self.rows[job_id][offset : offset + limit]
        valid_rows = sum(1 for row in self.rows[job_id] if row["validation_status"] == "VALID")
        invalid_rows = sum(1 for row in self.rows[job_id] if row["validation_status"] == "INVALID")
        return {
            "import_job_id": job_id,
            "counts": {
                "total_rows": len(self.rows[job_id]),
                "valid_rows": valid_rows,
                "invalid_rows": invalid_rows,
                "pending_rows": 0,
                "committed_rows": 0,
                "failed_rows": 0,
            },
            "items": items,
            "limit": limit,
            "offset": offset,
        }

    def get_errors(self, *, job_id: int, limit: int = 100, offset: int = 0) -> dict:
        items = self.errors.get(job_id, [])[offset : offset + limit]
        return {"import_job_id": job_id, "items": items, "limit": limit, "offset": offset}

    def get_audit(self, *, job_id: int, limit: int = 100, offset: int = 0) -> dict:
        _ = (job_id, limit, offset)
        return {"import_job_id": job_id, "items": []}

    def rollback_job(self, *, job_id: int, payload: dict) -> dict:
        _ = payload
        self.jobs[job_id]["job_status"] = "ROLLED_BACK"
        return {"import_job_id": job_id, "job_status": "ROLLED_BACK", "commit_status": "ROLLED_BACK"}

    def commit_job(self, *, job_id: int, payload: dict) -> dict:
        self.last_commit_payload = dict(payload)
        _ = payload
        valid_rows = [row for row in self.rows[job_id] if row["validation_status"] == "VALID"]
        for row in valid_rows:
            row["commit_status"] = "COMMITTED"
        self.jobs[job_id]["job_status"] = "COMMITTED"
        self.jobs[job_id]["commit_status"] = "COMMITTED"
        return {
            "import_job_id": job_id,
            "template_code": self.jobs[job_id]["template_code"],
            "committed_rows": len(valid_rows),
            "failed_rows": 0,
            "total_rows": len(valid_rows),
            "commit_status": "COMMITTED",
            "job_status": "COMMITTED",
        }


def _authorized_import_user() -> dict:
    return {
        "user_id": 42,
        "username": "import.bot",
        "roles": ["STAFF"],
        "permissions": ["imports:read", "imports:write", "imports:commit"],
    }


def _no_permission_user() -> dict:
    return {
        "user_id": 52,
        "username": "readonly.user",
        "roles": ["STUDENT"],
        "permissions": ["imports:read"],
    }


def test_import_api_create_upload_parse_validate_errors_and_commit() -> None:
    fake_service = FakeImportService()
    app.dependency_overrides[build_import_service] = lambda: fake_service
    app.dependency_overrides[require_imports_read] = _authorized_import_user
    app.dependency_overrides[require_imports_write] = _authorized_import_user
    app.dependency_overrides[require_imports_commit] = _authorized_import_user

    client = TestClient(app)
    try:
        create_resp = client.post(
            "/api/v1/imports/jobs",
            json={"template_code": "STUDENT_V1", "command_code": "IMPORT_VALIDATE"},
        )
        assert create_resp.status_code == 200
        job_id = create_resp.json()["data"]["import_job_id"]

        csv_bytes = b"student_code,full_name\nS001,Nguyen Van A\n"
        upload_resp = client.post(
            f"/api/v1/imports/jobs/{job_id}/upload",
            files={"file": ("students.csv", csv_bytes, "text/csv")},
        )
        assert upload_resp.status_code == 200
        assert upload_resp.json()["data"]["job_status"] == "UPLOADED"

        parse_resp = client.post(f"/api/v1/imports/jobs/{job_id}/parse")
        assert parse_resp.status_code == 200
        assert parse_resp.json()["data"]["job_status"] == "PARSED"

        validate_resp = client.post(f"/api/v1/imports/jobs/{job_id}/validate")
        assert validate_resp.status_code == 200
        assert validate_resp.json()["data"]["validation_status"] == "PASSED"

        errors_resp = client.get(f"/api/v1/imports/jobs/{job_id}/errors")
        assert errors_resp.status_code == 200
        assert errors_resp.json()["data"]["items"] == []

        commit_resp = client.post(
            f"/api/v1/imports/jobs/{job_id}/commit",
            json={"command_code": "IMPORT_COMMIT"},
        )
        assert commit_resp.status_code == 200
        assert commit_resp.json()["data"]["commit_status"] == "COMMITTED"
    finally:
        app.dependency_overrides.clear()


def test_import_api_get_template_by_code() -> None:
    fake_service = FakeImportService()
    app.dependency_overrides[build_import_service] = lambda: fake_service
    app.dependency_overrides[require_imports_read] = _authorized_import_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/imports/templates/STUDENT_V1")
        assert response.status_code == 200
        payload = response.json()["data"]["template"]
        assert payload["template_code"] == "STUDENT_V1"
    finally:
        app.dependency_overrides.clear()


def test_import_api_validation_errors_are_exposed() -> None:
    fake_service = FakeImportService()
    app.dependency_overrides[build_import_service] = lambda: fake_service
    app.dependency_overrides[require_imports_read] = _authorized_import_user
    app.dependency_overrides[require_imports_write] = _authorized_import_user

    client = TestClient(app)
    try:
        create_resp = client.post(
            "/api/v1/imports/jobs",
            json={"template_code": "STUDENT_V1", "command_code": "IMPORT_VALIDATE"},
        )
        job_id = create_resp.json()["data"]["import_job_id"]

        csv_bytes = b"student_code,full_name\nS001,\n"
        client.post(
            f"/api/v1/imports/jobs/{job_id}/upload",
            files={"file": ("students_invalid.csv", csv_bytes, "text/csv")},
        )
        client.post(f"/api/v1/imports/jobs/{job_id}/parse")
        validate_resp = client.post(f"/api/v1/imports/jobs/{job_id}/validate")

        assert validate_resp.status_code == 200
        assert validate_resp.json()["data"]["validation_status"] == "FAILED"

        errors_resp = client.get(f"/api/v1/imports/jobs/{job_id}/errors")
        assert errors_resp.status_code == 200
        items = errors_resp.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["error_code"] == "validation_error"
    finally:
        app.dependency_overrides.clear()


def test_import_job_create_rejects_anonymous() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/imports/jobs",
        json={"template_code": "STUDENT_V1", "command_code": "IMPORT_VALIDATE"},
    )

    assert response.status_code in {401, 403}


def test_import_commit_rejects_anonymous() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/imports/jobs/1/commit",
        json={"command_code": "IMPORT_COMMIT"},
    )

    assert response.status_code in {401, 403}


def test_import_commit_denied_without_commit_permission() -> None:
    def _deny_commit() -> dict:
        raise PermissionDeniedError("Missing required permission: imports:commit")

    app.dependency_overrides[require_imports_commit] = _deny_commit

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/imports/jobs/1/commit",
            json={"command_code": "IMPORT_COMMIT"},
        )
        assert response.status_code == 403
        payload = response.json()
        assert payload["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_import_actor_is_derived_from_authenticated_principal() -> None:
    fake_service = FakeImportService()
    app.dependency_overrides[build_import_service] = lambda: fake_service
    app.dependency_overrides[require_imports_write] = _authorized_import_user

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/imports/jobs",
            json={"template_code": "STUDENT_V1", "command_code": "IMPORT_VALIDATE"},
        )
        assert response.status_code == 200
        assert fake_service.last_create_payload is not None
        assert fake_service.last_create_payload["actor_user_id"] == 42
        assert fake_service.last_create_payload["actor_agent"] == "import.bot"
    finally:
        app.dependency_overrides.clear()


def test_import_actor_user_id_field_is_rejected() -> None:
    app.dependency_overrides[require_imports_write] = _authorized_import_user

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/imports/jobs",
            json={
                "template_code": "STUDENT_V1",
                "command_code": "IMPORT_VALIDATE",
                "actor_user_id": 999,
            },
        )
        assert response.status_code == 422
        payload = response.json()
        assert payload["error"]["code"] == "validation_error"
    finally:
        app.dependency_overrides.clear()
