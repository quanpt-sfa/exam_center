"""Service tests for student file-answer upload workflows."""

from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest
from starlette.datastructures import Headers
from starlette.datastructures import UploadFile

from app.core.errors import ApiError
from app.modules.submission.services.submission_service import SubmissionService


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
                            "text/json",
                        ],
                        "allowed_extensions": [".zip", ".pdf", ".docx", ".xlsx", ".csv", ".sql", ".txt", ".json"],
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
        self.next_seal_id = 1
        self.next_sealed_answer_id = 1
        self.sealed_answers: list[dict] = []

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

    def list_submission_question_seal_requirements(self, submission_id: int) -> list[dict]:
        rows: list[dict] = []
        for question_id, question in self.questions.items():
            if (submission_id, question_id) in self.answer_states:
                answer_state = self.answer_states[(submission_id, question_id)]
            else:
                answer_state = None

            active_asset = None
            for asset in self.file_assets:
                if (
                    int(asset["exam_submission_id"]) == int(submission_id)
                    and int(asset["generated_exam_question_id"]) == int(question_id)
                    and str(asset["asset_status"]).upper() == "ACTIVE"
                ):
                    active_asset = asset
                    break

            payload = question.get("rendered_question_payload_json")
            answer_ui = payload.get("answer_ui") if isinstance(payload, dict) else None
            answer_ui = answer_ui if isinstance(answer_ui, dict) else {}
            input_source = str(answer_ui.get("input_source") or "").strip().upper()
            if not input_source and str(question.get("question_type") or "").strip().upper() == "FILE_UPLOAD":
                input_source = "SEALED_FILE_REF"

            rows.append(
                {
                    "generated_exam_question_id": int(question_id),
                    "question_order": 1,
                    "question_type": question.get("question_type"),
                    "rendered_question_payload_json": deepcopy(payload) if isinstance(payload, dict) else {},
                    "input_source": input_source,
                    "grading_profile_metadata_json": {},
                    "answer_state_id": int(answer_state["answer_state_id"]) if answer_state is not None else None,
                    "answer_type": answer_state.get("answer_type") if answer_state is not None else None,
                    "answer_payload_json": deepcopy(answer_state.get("answer_payload_json")) if answer_state is not None else None,
                    "answer_file_asset_id": int(active_asset["answer_file_asset_id"]) if active_asset is not None else None,
                    "asset_status": active_asset.get("asset_status") if active_asset is not None else None,
                    "asset_submission_id": int(active_asset["exam_submission_id"]) if active_asset is not None else None,
                    "asset_question_id": int(active_asset["generated_exam_question_id"]) if active_asset is not None else None,
                }
            )
        return rows

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
        changed = 0
        for row in self.file_assets:
            if (
                int(row["exam_submission_id"]) == int(submission_id)
                and int(row["generated_exam_question_id"]) == int(generated_exam_question_id)
                and str(row["asset_status"]) == "ACTIVE"
            ):
                row["asset_status"] = "SUPERSEDED"
                row["superseded_at"] = datetime.now(timezone.utc)
                row["superseded_by"] = superseded_by
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
        existing = self.answer_states.get(key)
        if existing is None:
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

        existing["answer_type"] = answer_type
        existing["answer_text"] = answer_text
        existing["answer_payload_json"] = answer_payload_json
        existing["answer_hash"] = answer_hash
        existing["answer_length"] = answer_length
        existing["client_version"] = client_version
        existing["server_version"] = int(existing["server_version"]) + 1
        existing["client_saved_at"] = client_saved_at
        existing["last_saved_at"] = datetime.now(timezone.utc)
        return deepcopy(existing)

    def attach_answer_state_to_file_asset(self, *, answer_file_asset_id: int, answer_state_id: int) -> None:
        for row in self.file_assets:
            if int(row["answer_file_asset_id"]) == int(answer_file_asset_id):
                row["answer_state_id"] = int(answer_state_id)
                return
        raise RuntimeError("file asset not found")

    def update_submission_after_autosave(self, submission_id: int) -> None:
        row = self.submissions[submission_id]
        if row.get("first_saved_at") is None:
            row["first_saved_at"] = datetime.now(timezone.utc)
        row["last_saved_at"] = datetime.now(timezone.utc)
        if str(row.get("submission_status")) == "DRAFT":
            row["submission_status"] = "IN_PROGRESS"

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

    def get_answer_state_count(self, submission_id: int) -> int:
        return sum(1 for (sid, _), _row in self.answer_states.items() if sid == submission_id)

    def create_submission_seal(
        self,
        *,
        submission_id: int,
        seal_idempotency_key: str,
        seal_status: str,
        seal_reason: str,
        sealed_by: int | None,
        answer_count: int,
        submission_hash: str | None,
        metadata_json: dict | None,
    ) -> dict:
        _ = metadata_json
        seal = {
            "submission_seal_id": self.next_seal_id,
            "exam_submission_id": submission_id,
            "seal_idempotency_key": seal_idempotency_key,
            "seal_status": seal_status,
            "seal_reason": seal_reason,
            "sealed_at": datetime.now(timezone.utc),
            "sealed_by": sealed_by,
            "answer_count": answer_count,
            "submission_hash": submission_hash,
        }
        self.seals[submission_id] = seal
        self.next_seal_id += 1
        return deepcopy(seal)

    def create_sealed_answers_from_state(self, *, submission_id: int, submission_seal_id: int) -> int:
        inserted = 0
        for (sid, qid), state in self.answer_states.items():
            if sid != submission_id:
                continue
            self.sealed_answers.append(
                {
                    "sealed_answer_id": self.next_sealed_answer_id,
                    "submission_seal_id": submission_seal_id,
                    "exam_submission_id": sid,
                    "generated_exam_question_id": qid,
                    "answer_type": state["answer_type"],
                    "answer_payload_json": deepcopy(state.get("answer_payload_json")),
                    "answer_hash": state.get("answer_hash"),
                    "answer_length": state.get("answer_length"),
                }
            )
            self.next_sealed_answer_id += 1
            inserted += 1
        return inserted

    def mark_sealed_file_assets(self, *, submission_id: int, submission_seal_id: int) -> int:
        changed = 0
        by_question: dict[int, int] = {}
        for row in self.sealed_answers:
            if (
                int(row["exam_submission_id"]) == int(submission_id)
                and int(row["submission_seal_id"]) == int(submission_seal_id)
                and str(row["answer_type"]) == "FILE_REF"
            ):
                by_question[int(row["generated_exam_question_id"])] = int(row["sealed_answer_id"])

        for asset in self.file_assets:
            qid = int(asset["generated_exam_question_id"])
            if (
                int(asset["exam_submission_id"]) == int(submission_id)
                and str(asset["asset_status"]) == "ACTIVE"
                and qid in by_question
            ):
                asset["asset_status"] = "SEALED"
                asset["submission_seal_id"] = int(submission_seal_id)
                asset["sealed_answer_id"] = int(by_question[qid])
                changed += 1
        return changed

    def update_submission_after_seal(self, *, submission_id: int, submission_status: str, seal_reason: str) -> None:
        row = self.submissions[submission_id]
        row["submission_status"] = submission_status
        row["seal_reason"] = seal_reason
        row["sealed_at"] = datetime.now(timezone.utc)
        if row["submitted_at"] is None:
            row["submitted_at"] = datetime.now(timezone.utc)

    def get_seal_summary(self, submission_id: int) -> dict | None:
        seal = self.seals.get(submission_id)
        if seal is None:
            return None
        sealed_answer_count = sum(1 for row in self.sealed_answers if int(row["exam_submission_id"]) == int(submission_id))
        return {
            "submission_seal_id": seal["submission_seal_id"],
            "exam_submission_id": submission_id,
            "submission_status": self.submissions[submission_id]["submission_status"],
            "seal_status": seal["seal_status"],
            "seal_reason": seal["seal_reason"],
            "sealed_at": seal["sealed_at"],
            "answer_count": seal["answer_count"],
            "submission_hash": seal["submission_hash"],
            "sealed_answer_count": sealed_answer_count,
        }


def _student_user() -> dict:
    return {"user_id": 10, "roles": ["STUDENT"]}


def _build_upload(filename: str, content_type: str, payload: bytes) -> UploadFile:
    return UploadFile(file=BytesIO(payload), filename=filename, headers=Headers({"content-type": content_type}))


@pytest.mark.asyncio
async def test_valid_upload_creates_file_asset_and_answer_state_file_ref(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", str(tmp_path))
    repo = InMemoryFileSubmissionRepository()
    service = SubmissionService(repository=repo, transaction_scope=lambda: nullcontext())

    uploaded = await service.upload_answer_file(
        submission_id=1,
        generated_exam_question_id=501,
        upload_file=_build_upload("bai_lam.zip", "application/zip", b"PK\x03\x04demo-zip-content"),
        metadata_json={"source": "unit"},
        current_user=_student_user(),
    )

    assert uploaded["submission_id"] == 1
    assert uploaded["generated_exam_question_id"] == 501
    assert uploaded["answer_file"]["status"] == "ACTIVE"
    assert "internal_storage_key" not in str(uploaded).lower()
    assert "stored_filename" not in str(uploaded).lower()

    state = repo.answer_states[(1, 501)]
    assert state["answer_type"] == "FILE_REF"
    assert state["answer_text"] is None
    assert isinstance(state["answer_payload_json"], dict)
    assert int(state["answer_payload_json"]["file_asset_id"]) > 0


@pytest.mark.asyncio
async def test_replace_upload_supersedes_previous_asset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", str(tmp_path))
    repo = InMemoryFileSubmissionRepository()
    service = SubmissionService(repository=repo, transaction_scope=lambda: nullcontext())

    await service.upload_answer_file(
        submission_id=1,
        generated_exam_question_id=501,
        upload_file=_build_upload("b1.zip", "application/zip", b"PK\x03\x04first"),
        metadata_json=None,
        current_user=_student_user(),
    )
    second = await service.upload_answer_file(
        submission_id=1,
        generated_exam_question_id=501,
        upload_file=_build_upload("b2.zip", "application/zip", b"PK\x03\x04second"),
        metadata_json=None,
        current_user=_student_user(),
    )

    assert int(second["answer_file"]["file_asset_id"]) == 2
    first_asset = next(row for row in repo.file_assets if int(row["answer_file_asset_id"]) == 1)
    second_asset = next(row for row in repo.file_assets if int(row["answer_file_asset_id"]) == 2)
    assert first_asset["asset_status"] == "SUPERSEDED"
    assert second_asset["asset_status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_upload_after_seal_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", str(tmp_path))
    repo = InMemoryFileSubmissionRepository()
    service = SubmissionService(repository=repo, transaction_scope=lambda: nullcontext())

    repo.seals[1] = {
        "submission_seal_id": 77,
        "exam_submission_id": 1,
        "seal_status": "SEALED",
        "seal_reason": "STUDENT_SUBMIT",
    }

    with pytest.raises(ApiError) as exc:
        await service.upload_answer_file(
            submission_id=1,
            generated_exam_question_id=501,
            upload_file=_build_upload("b1.zip", "application/zip", b"PK\x03\x04sealed"),
            metadata_json=None,
            current_user=_student_user(),
        )
    assert exc.value.code == "SUBMISSION_ALREADY_SEALED"


@pytest.mark.asyncio
async def test_invalid_extension_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", str(tmp_path))
    repo = InMemoryFileSubmissionRepository()
    service = SubmissionService(repository=repo, transaction_scope=lambda: nullcontext())

    with pytest.raises(ApiError) as exc:
        await service.upload_answer_file(
            submission_id=1,
            generated_exam_question_id=501,
            upload_file=_build_upload("evil.exe", "application/octet-stream", b"MZpayload"),
            metadata_json=None,
            current_user=_student_user(),
        )
    assert exc.value.code == "UNSUPPORTED_FILE_TYPE"


@pytest.mark.asyncio
async def test_dangerous_powershell_extension_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", str(tmp_path))
    repo = InMemoryFileSubmissionRepository()
    service = SubmissionService(repository=repo, transaction_scope=lambda: nullcontext())

    with pytest.raises(ApiError) as exc:
        await service.upload_answer_file(
            submission_id=1,
            generated_exam_question_id=501,
            upload_file=_build_upload("run.ps1", "text/plain", b"Write-Host hacked"),
            metadata_json=None,
            current_user=_student_user(),
        )
    assert exc.value.code == "UNSUPPORTED_FILE_TYPE"


@pytest.mark.asyncio
async def test_oversized_file_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_MAX_BYTES", "8")
    repo = InMemoryFileSubmissionRepository()
    repo.questions[501]["rendered_question_payload_json"]["answer_ui"]["max_file_size_bytes"] = 8
    service = SubmissionService(repository=repo, transaction_scope=lambda: nullcontext())

    with pytest.raises(ApiError) as exc:
        await service.upload_answer_file(
            submission_id=1,
            generated_exam_question_id=501,
            upload_file=_build_upload("big.zip", "application/zip", b"PK\x03\x04abcdefghi"),
            metadata_json=None,
            current_user=_student_user(),
        )
    assert exc.value.code == "FILE_TOO_LARGE"


@pytest.mark.asyncio
async def test_docx_and_xlsx_are_accepted_with_official_mime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", str(tmp_path))
    repo = InMemoryFileSubmissionRepository()
    service = SubmissionService(repository=repo, transaction_scope=lambda: nullcontext())

    docx = await service.upload_answer_file(
        submission_id=1,
        generated_exam_question_id=501,
        upload_file=_build_upload(
            "bai_lam.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            b"PK\x03\x04docx-content",
        ),
        metadata_json=None,
        current_user=_student_user(),
    )
    xlsx = await service.upload_answer_file(
        submission_id=1,
        generated_exam_question_id=501,
        upload_file=_build_upload(
            "bang_diem.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            b"PK\x03\x04xlsx-content",
        ),
        metadata_json=None,
        current_user=_student_user(),
    )

    assert docx["answer_file"]["mime_type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert xlsx["answer_file"]["mime_type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.mark.asyncio
async def test_csv_and_sql_are_accepted_with_text_plain(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", str(tmp_path))
    repo = InMemoryFileSubmissionRepository()
    service = SubmissionService(repository=repo, transaction_scope=lambda: nullcontext())

    csv_uploaded = await service.upload_answer_file(
        submission_id=1,
        generated_exam_question_id=501,
        upload_file=_build_upload("data.csv", "text/plain", b"id,name\n1,A"),
        metadata_json=None,
        current_user=_student_user(),
    )
    csv_with_text_csv = await service.upload_answer_file(
        submission_id=1,
        generated_exam_question_id=501,
        upload_file=_build_upload("data2.csv", "text/csv", b"id,name\n2,B"),
        metadata_json=None,
        current_user=_student_user(),
    )
    sql_uploaded = await service.upload_answer_file(
        submission_id=1,
        generated_exam_question_id=501,
        upload_file=_build_upload("query.sql", "text/plain", b"select 1;"),
        metadata_json=None,
        current_user=_student_user(),
    )

    assert csv_uploaded["answer_file"]["mime_type"] in {"text/plain", "text/csv", "application/csv"}
    assert csv_with_text_csv["answer_file"]["mime_type"] in {"text/plain", "text/csv", "application/csv"}
    assert sql_uploaded["answer_file"]["mime_type"] in {"text/plain", "application/sql", "application/octet-stream"}


@pytest.mark.asyncio
async def test_pdf_with_invalid_signature_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", str(tmp_path))
    repo = InMemoryFileSubmissionRepository()
    service = SubmissionService(repository=repo, transaction_scope=lambda: nullcontext())

    with pytest.raises(ApiError) as exc:
        await service.upload_answer_file(
            submission_id=1,
            generated_exam_question_id=501,
            upload_file=_build_upload("fake.pdf", "text/plain", b"not-a-real-pdf"),
            metadata_json=None,
            current_user=_student_user(),
        )
    assert exc.value.code == "UNSUPPORTED_FILE_TYPE"


@pytest.mark.asyncio
async def test_seal_snapshots_file_ref_into_sealed_answer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_ANSWER_FILE_STORAGE_ROOT", str(tmp_path))
    repo = InMemoryFileSubmissionRepository()
    service = SubmissionService(repository=repo, transaction_scope=lambda: nullcontext())

    await service.upload_answer_file(
        submission_id=1,
        generated_exam_question_id=501,
        upload_file=_build_upload("b1.zip", "application/zip", b"PK\x03\x04seal-me"),
        metadata_json=None,
        current_user=_student_user(),
    )

    sealed = service.seal_submission(
        submission_id=1,
        payload={
            "seal_idempotency_key": "seal-file-1",
            "seal_reason": "STUDENT_SUBMIT",
            "metadata_json": {},
        },
        current_user=_student_user(),
    )

    assert sealed["sealed_answer_count"] == 1
    sealed_answer = repo.sealed_answers[0]
    assert sealed_answer["answer_type"] == "FILE_REF"
    assert "file_asset_id" in (sealed_answer.get("answer_payload_json") or {})
    asset = repo.file_assets[-1]
    assert asset["asset_status"] == "SEALED"
    assert int(asset["submission_seal_id"]) == int(repo.seals[1]["submission_seal_id"])
