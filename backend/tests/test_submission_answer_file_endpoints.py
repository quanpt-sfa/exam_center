"""Endpoint tests for student answer-file APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.modules.submission.permissions import require_submission_access
from app.modules.submission.permissions import require_student_submission_access
from app.modules.submission.services.submission_service import SubmissionService, build_submission_service


class InMemoryFileSubmissionRepository:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.submissions = {
            1: {
                "exam_submission_id": 1,
                "exam_session_id": 21,
                "generated_exam_instance_id": 9001,
                "submission_status": "IN_PROGRESS",
                "opened_at": now,
                "first_saved_at": now,
                "last_saved_at": now,
                "submitted_at": None,
                "sealed_at": None,
                "seal_reason": None,
                "student_id": 100,
            }
        }
        self.user_student_map = {10: 100, 11: 101}
        self.seals: dict[int, dict] = {}
        self.questions: dict[int, dict] = {
            501: {
                "generated_exam_question_id": 501,
                "question_type": "FILE_UPLOAD",
                "rendered_question_payload_json": {
                    "answer_ui": {
                        "ui_mode": "FILE_UPLOAD",
                        "input_source": "SEALED_FILE_REF",
                        "allowed_mime_types": ["application/zip", "application/pdf", "text/plain", "application/json"],
                        "allowed_extensions": [".zip", ".pdf", ".txt", ".json"],
                        "max_file_size_bytes": 1024 * 1024,
                        "required": True,
                    }
                },
            }
        }
        self.answer_states: dict[tuple[int, int], dict] = {}
        self.file_assets: list[dict] = []
        self.next_asset_id = 1
        self.next_answer_state_id = 1

    def get_submission_by_id(self, submission_id: int) -> dict | None:
        row = self.submissions.get(submission_id)
        return dict(row) if row else None

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        return self.user_student_map.get(user_id)

    def get_seal_by_submission_id(self, submission_id: int) -> dict | None:
        row = self.seals.get(submission_id)
        return dict(row) if row else None

    def get_submission_question_detail(self, *, submission_id: int, generated_exam_question_id: int) -> dict | None:
        _ = submission_id
        row = self.questions.get(generated_exam_question_id)
        return deepcopy(row) if row else None

    def get_max_server_revision(self, submission_id: int) -> int:
        revisions = [int(row["server_version"]) for (sid, _), row in self.answer_states.items() if sid == submission_id]
        return max(revisions) if revisions else 0

    def supersede_active_answer_file_assets(
        self,
        *,
        submission_id: int,
        generated_exam_question_id: int,
        superseded_by: int | None,
    ) -> int:
        _ = superseded_by
        changed = 0
        for row in self.file_assets:
            if (
                int(row["exam_submission_id"]) == int(submission_id)
                and int(row["generated_exam_question_id"]) == int(generated_exam_question_id)
                and str(row["asset_status"]) == "ACTIVE"
            ):
                row["asset_status"] = "SUPERSEDED"
                changed += 1
        return changed

    def create_answer_file_asset(
        self,
        *,
        submission_id: int,
        generated_exam_question_id: int,
        answer_state_id: int | None,
        original_filename: str,
        stored_filename: str,
        internal_storage_key: str,
        mime_type: str,
        file_size_bytes: int,
        sha256_hash: str,
        uploaded_by: int | None,
        metadata_json: dict | None,
    ) -> dict:
        row = {
            "answer_file_asset_id": self.next_asset_id,
            "exam_submission_id": submission_id,
            "generated_exam_question_id": generated_exam_question_id,
            "answer_state_id": answer_state_id,
            "submission_seal_id": None,
            "sealed_answer_id": None,
            "original_filename": original_filename,
            "stored_filename": stored_filename,
            "internal_storage_key": internal_storage_key,
            "mime_type": mime_type,
            "file_size_bytes": file_size_bytes,
            "sha256_hash": sha256_hash,
            "asset_status": "ACTIVE",
            "uploaded_at": datetime.now(timezone.utc),
            "uploaded_by": uploaded_by,
            "superseded_at": None,
            "superseded_by": None,
            "metadata_json": metadata_json or {},
        }
        self.file_assets.append(row)
        self.next_asset_id += 1
        return deepcopy(row)

    def upsert_answer_state(
        self,
        *,
        submission_id: int,
        generated_exam_question_id: int,
        answer_type: str,
        answer_text: str | None,
        answer_payload_json: dict | None,
        answer_hash: str | None,
        answer_length: int | None,
        client_version: int,
        client_saved_at: datetime | None,
        device_id: int | None,
        station_id: int | None,
        metadata_json: dict | None,
    ) -> dict:
        _ = (device_id, station_id, metadata_json)
        key = (submission_id, generated_exam_question_id)
        row = self.answer_states.get(key)
        if row is None:
            row = {
                "answer_state_id": self.next_answer_state_id,
                "exam_submission_id": submission_id,
                "generated_exam_question_id": generated_exam_question_id,
                "answer_type": answer_type,
                "answer_text": answer_text,
                "answer_payload_json": answer_payload_json,
                "answer_hash": answer_hash,
                "answer_length": answer_length,
                "client_version": client_version,
                "server_version": 1,
                "client_saved_at": client_saved_at,
                "last_saved_at": datetime.now(timezone.utc),
                "answer_status": "DRAFT",
            }
            self.answer_states[key] = row
            self.next_answer_state_id += 1
            return deepcopy(row)
        row["answer_type"] = answer_type
        row["answer_text"] = answer_text
        row["answer_payload_json"] = answer_payload_json
        row["answer_hash"] = answer_hash
        row["answer_length"] = answer_length
        row["client_version"] = client_version
        row["server_version"] = int(row["server_version"]) + 1
        row["client_saved_at"] = client_saved_at
        row["last_saved_at"] = datetime.now(timezone.utc)
        return deepcopy(row)

    def attach_answer_state_to_file_asset(self, *, answer_file_asset_id: int, answer_state_id: int) -> None:
        for row in self.file_assets:
            if int(row["answer_file_asset_id"]) == int(answer_file_asset_id):
                row["answer_state_id"] = int(answer_state_id)
                return

    def update_submission_after_autosave(self, submission_id: int) -> None:
        row = self.submissions[submission_id]
        row["last_saved_at"] = datetime.now(timezone.utc)

    def get_current_answer_file_asset(self, *, submission_id: int, generated_exam_question_id: int) -> dict | None:
        candidates = [
            row
            for row in self.file_assets
            if int(row["exam_submission_id"]) == int(submission_id)
            and int(row["generated_exam_question_id"]) == int(generated_exam_question_id)
            and str(row["asset_status"]) in {"ACTIVE", "SEALED"}
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda item: int(item["answer_file_asset_id"]), reverse=True)
        return deepcopy(candidates[0])


def _student_user() -> dict:
    return {"user_id": 10, "roles": ["STUDENT"]}


def _other_student_user() -> dict:
    return {"user_id": 11, "roles": ["STUDENT"]}


def test_upload_and_get_metadata_and_stream_content(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", str(tmp_path))
    repo = InMemoryFileSubmissionRepository()
    service = SubmissionService(repository=repo)

    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_submission_access] = _student_user
    app.dependency_overrides[require_student_submission_access] = _student_user
    client = TestClient(app)

    try:
        upload = client.post(
            "/api/v1/submissions/1/answers/501/file",
            files={"file": ("bai_lam.zip", b"PK\x03\x04upload", "application/zip")},
            data={"metadata_json": '{"source":"endpoint"}'},
        )
        assert upload.status_code == 200
        upload_data = upload.json()["data"]
        assert upload_data["answer_file"]["status"] == "ACTIVE"
        assert "internal_storage_key" not in str(upload_data).lower()
        assert "stored_filename" not in str(upload_data).lower()
        assert "expected_answer" not in str(upload_data).lower()

        metadata = client.get("/api/v1/submissions/1/answers/501/file")
        assert metadata.status_code == 200
        meta_data = metadata.json()["data"]
        assert meta_data["answer_file"]["file_name"] == "bai_lam.zip"
        assert "internal_storage_key" not in str(meta_data).lower()

        content = client.get("/api/v1/submissions/1/answers/501/file/content")
        assert content.status_code == 200
        assert content.headers.get("cache-control") == "no-store"
        assert content.headers.get("x-content-type-options") == "nosniff"
        assert "content-disposition" in content.headers
        assert content.content == b"PK\x03\x04upload"
    finally:
        app.dependency_overrides.clear()


def test_replace_upload_supersedes_previous_asset(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", str(tmp_path))
    repo = InMemoryFileSubmissionRepository()
    service = SubmissionService(repository=repo)
    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_submission_access] = _student_user
    app.dependency_overrides[require_student_submission_access] = _student_user
    client = TestClient(app)

    try:
        first = client.post(
            "/api/v1/submissions/1/answers/501/file",
            files={"file": ("old.zip", b"PK\x03\x04old", "application/zip")},
        )
        assert first.status_code == 200
        second = client.post(
            "/api/v1/submissions/1/answers/501/file",
            files={"file": ("new.zip", b"PK\x03\x04new", "application/zip")},
        )
        assert second.status_code == 200
        statuses = [row["asset_status"] for row in repo.file_assets]
        assert statuses.count("SUPERSEDED") == 1
        assert statuses.count("ACTIVE") == 1
    finally:
        app.dependency_overrides.clear()


def test_unauthorized_student_is_denied(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", str(tmp_path))
    repo = InMemoryFileSubmissionRepository()
    service = SubmissionService(repository=repo)
    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_submission_access] = _other_student_user
    app.dependency_overrides[require_student_submission_access] = _other_student_user
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/submissions/1/answers/501/file",
            files={"file": ("file.zip", b"PK\x03\x04x", "application/zip")},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_upload_after_seal_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", str(tmp_path))
    repo = InMemoryFileSubmissionRepository()
    repo.seals[1] = {
        "submission_seal_id": 901,
        "exam_submission_id": 1,
        "seal_status": "SEALED",
        "seal_reason": "STUDENT_SUBMIT",
    }
    service = SubmissionService(repository=repo)
    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_submission_access] = _student_user
    app.dependency_overrides[require_student_submission_access] = _student_user
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/submissions/1/answers/501/file",
            files={"file": ("file.zip", b"PK\x03\x04x", "application/zip")},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "SUBMISSION_ALREADY_SEALED"
    finally:
        app.dependency_overrides.clear()


def test_invalid_extension_and_oversized_file_are_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_MAX_BYTES", "8")
    repo = InMemoryFileSubmissionRepository()
    repo.questions[501]["rendered_question_payload_json"]["answer_ui"]["max_file_size_bytes"] = 8
    service = SubmissionService(repository=repo)
    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_submission_access] = _student_user
    app.dependency_overrides[require_student_submission_access] = _student_user
    client = TestClient(app)

    try:
        bad_ext = client.post(
            "/api/v1/submissions/1/answers/501/file",
            files={"file": ("evil.exe", b"MZbad", "application/octet-stream")},
        )
        assert bad_ext.status_code == 422
        assert bad_ext.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"

        too_big = client.post(
            "/api/v1/submissions/1/answers/501/file",
            files={"file": ("big.zip", b"PK\x03\x04abcdefghi", "application/zip")},
        )
        assert too_big.status_code == 413
        assert too_big.json()["error"]["code"] == "FILE_TOO_LARGE"
    finally:
        app.dependency_overrides.clear()


def test_upload_rejects_unknown_generated_exam_question_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", str(tmp_path))
    repo = InMemoryFileSubmissionRepository()
    service = SubmissionService(repository=repo)
    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_submission_access] = _student_user
    app.dependency_overrides[require_student_submission_access] = _student_user
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/submissions/1/answers/999999/file",
            files={"file": ("bai_lam.zip", b"PK\x03\x04upload", "application/zip")},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "QUESTION_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()
