"""Service tests for submission autosave and seal semantics."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.core.errors import ApiError
from app.modules.submission.services.submission_service import SubmissionService


class InMemorySubmissionRepository:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.submissions: dict[int, dict] = {
            1: {
                "exam_submission_id": 1,
                "exam_session_id": 20,
                "generated_exam_instance_id": 7001,
                "submission_status": "DRAFT",
                "opened_at": now,
                "first_saved_at": None,
                "last_saved_at": None,
                "submitted_at": None,
                "sealed_at": None,
                "seal_reason": None,
                "student_id": 100,
                "session_status": "IN_PROGRESS",
                "deadline_at": now.replace(year=now.year + 1),
                "exam_sitting_room_id": 300,
                "room_status": "OPEN",
            }
        }
        self.user_student_map = {10: 100, 11: 101}
        self.answer_states: dict[tuple[int, int], dict] = {}
        self.batches: dict[tuple[int, str], dict] = {}
        self.batch_items: dict[int, list[dict]] = {}
        self.seals: dict[int, dict] = {}
        self.sealed_answers: dict[tuple[int, int], dict] = {}
        self.next_batch_id = 1
        self.next_item_id = 1
        self.next_answer_state_id = 1
        self.next_seal_id = 1
        self.seal_requirements_rows: list[dict] = []
        self.submission_history: list[dict] = []
        self.proctor_assignments: dict[tuple[int, int], str] = {(300, 20): "ASSIGNED"}
        self.submission_questions: dict[int, dict[int, dict]] = {
            1: {
                101: {
                    "generated_exam_question_id": 101,
                    "question_type": "SQL_QUERY",
                    "rendered_question_payload_json": {"answer_ui": {"ui_mode": "TEXTAREA"}},
                },
                202: {
                    "generated_exam_question_id": 202,
                    "question_type": "MULTIPLE_CHOICE",
                    "rendered_question_payload_json": {"answer_ui": {"ui_mode": "MCQ_SINGLE"}},
                },
            }
        }
        self.generated_option_details: dict[tuple[int, int, int], dict] = {
            (1, 202, 1001): {
                "generated_exam_question_id": 202,
                "question_type": "MULTIPLE_CHOICE",
                "generated_exam_option_id": 1001,
                "original_option_id": 1,
                "option_order": 1,
                "option_label": "A",
                "rendered_option_text": "A. 10",
            },
            (1, 202, 1002): {
                "generated_exam_question_id": 202,
                "question_type": "MULTIPLE_CHOICE",
                "generated_exam_option_id": 1002,
                "original_option_id": 2,
                "option_order": 2,
                "option_label": "B",
                "rendered_option_text": "B. 20",
            },
            (1, 202, 1003): {
                "generated_exam_question_id": 202,
                "question_type": "MULTIPLE_CHOICE",
                "generated_exam_option_id": 1003,
                "original_option_id": 3,
                "option_order": 3,
                "option_label": "C",
                "rendered_option_text": "C. 30",
            },
        }

    def get_submission_by_id(self, submission_id: int) -> dict | None:
        return self.submissions.get(submission_id)

    def get_submission_runtime_policy_context(self, submission_id: int) -> dict | None:
        row = self.submissions.get(submission_id)
        return dict(row) if row is not None else None

    def get_submission_runtime_contract_context(self, submission_id: int) -> dict | None:
        return self.get_submission_runtime_policy_context(submission_id)

    def lock_submission_runtime_policy_context(self, submission_id: int) -> dict | None:
        return self.get_submission_runtime_policy_context(submission_id)

    def is_proctor_assigned_to_room(self, *, exam_sitting_room_id: int, proctor_user_id: int) -> bool:
        status = self.proctor_assignments.get((int(exam_sitting_room_id), int(proctor_user_id)))
        return status in {"ASSIGNED", "CONFIRMED"}

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        return self.user_student_map.get(user_id)

    def get_seal_by_submission_id(self, submission_id: int) -> dict | None:
        return self.seals.get(submission_id)

    def get_batch_by_idempotency(self, *, submission_id: int, idempotency_key: str) -> dict | None:
        return self.batches.get((submission_id, idempotency_key))

    def create_answer_save_batch(
        self,
        *,
        submission_id: int,
        idempotency_key: str,
        client_sequence_no: int | None,
        client_saved_at: datetime | None,
        device_id: int | None,
        station_id: int | None,
        batch_status: str,
        accepted_item_count: int,
        rejected_item_count: int,
        metadata_json: dict | None,
    ) -> dict:
        row = {
            "answer_save_batch_id": self.next_batch_id,
            "exam_submission_id": submission_id,
            "idempotency_key": idempotency_key,
            "client_sequence_no": client_sequence_no,
            "client_saved_at": client_saved_at,
            "server_received_at": datetime.now(timezone.utc),
            "device_id": device_id,
            "station_id": station_id,
            "batch_status": batch_status,
            "accepted_item_count": accepted_item_count,
            "rejected_item_count": rejected_item_count,
            "metadata_json": metadata_json,
        }
        self.batches[(submission_id, idempotency_key)] = row
        self.batch_items[self.next_batch_id] = []
        self.next_batch_id += 1
        return row

    def update_answer_save_batch(
        self,
        *,
        answer_save_batch_id: int,
        batch_status: str,
        accepted_item_count: int,
        rejected_item_count: int,
    ) -> dict | None:
        for row in self.batches.values():
            if int(row["answer_save_batch_id"]) == answer_save_batch_id:
                row["batch_status"] = batch_status
                row["accepted_item_count"] = accepted_item_count
                row["rejected_item_count"] = rejected_item_count
                return row
        return None

    def create_answer_save_item(
        self,
        *,
        answer_save_batch_id: int,
        generated_exam_question_id: int,
        answer_state_id: int | None,
        client_version: int | None,
        server_version: int | None,
        answer_hash: str | None,
        answer_length: int | None,
        item_status: str,
        error_code: str | None,
        error_message: str | None,
    ) -> dict:
        row = {
            "answer_save_item_id": self.next_item_id,
            "answer_save_batch_id": answer_save_batch_id,
            "generated_exam_question_id": generated_exam_question_id,
            "answer_state_id": answer_state_id,
            "client_version": client_version,
            "server_version": server_version,
            "answer_hash": answer_hash,
            "answer_length": answer_length,
            "item_status": item_status,
            "saved_at": datetime.now(timezone.utc),
            "error_code": error_code,
            "error_message": error_message,
        }
        self.batch_items[answer_save_batch_id].append(row)
        self.next_item_id += 1
        return row

    def list_answer_save_items(self, *, answer_save_batch_id: int) -> list[dict]:
        return list(self.batch_items.get(answer_save_batch_id, []))

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
            server_version = 1
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
                "server_version": server_version,
                "client_saved_at": client_saved_at,
                "last_saved_at": datetime.now(timezone.utc),
                "answer_status": "DRAFT",
            }
            self.answer_states[key] = row
            self.next_answer_state_id += 1
            return row

        existing["answer_type"] = answer_type
        existing["answer_text"] = answer_text
        existing["answer_payload_json"] = answer_payload_json
        existing["answer_hash"] = answer_hash
        existing["answer_length"] = answer_length
        existing["client_version"] = client_version
        existing["server_version"] = int(existing["server_version"]) + 1
        existing["client_saved_at"] = client_saved_at
        existing["last_saved_at"] = datetime.now(timezone.utc)
        return existing

    def list_answer_state(self, submission_id: int) -> list[dict]:
        rows: list[dict] = []
        for (sub_id, question_id), row in self.answer_states.items():
            if sub_id != submission_id:
                continue
            copy_row = dict(row)
            copy_row["question_order"] = question_id
            rows.append(copy_row)
        rows.sort(key=lambda item: int(item["generated_exam_question_id"]))
        return rows

    def get_submission_question_detail(self, *, submission_id: int, generated_exam_question_id: int) -> dict | None:
        submission_questions = self.submission_questions.get(int(submission_id), {})
        row = submission_questions.get(int(generated_exam_question_id))
        return dict(row) if row is not None else None

    def get_generated_option_selection_detail(
        self,
        *,
        submission_id: int,
        generated_exam_question_id: int,
        generated_exam_option_id: int,
    ) -> dict | None:
        row = self.generated_option_details.get(
            (int(submission_id), int(generated_exam_question_id), int(generated_exam_option_id))
        )
        return dict(row) if row is not None else None

    def get_max_server_revision(self, submission_id: int) -> int:
        revisions = [
            int(row["server_version"])
            for (sub_id, _), row in self.answer_states.items()
            if sub_id == submission_id
        ]
        return max(revisions) if revisions else 0

    def get_answer_state_count(self, submission_id: int) -> int:
        return sum(1 for (sub_id, _) in self.answer_states if sub_id == submission_id)

    def update_submission_after_autosave(self, submission_id: int) -> None:
        submission = self.submissions[submission_id]
        if submission["first_saved_at"] is None:
            submission["first_saved_at"] = datetime.now(timezone.utc)
        submission["last_saved_at"] = datetime.now(timezone.utc)
        if submission["submission_status"] == "DRAFT":
            submission["submission_status"] = "IN_PROGRESS"

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
        row = {
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
        self.seals[submission_id] = row
        self.next_seal_id += 1
        return row

    def create_sealed_answers_from_state(self, *, submission_id: int, submission_seal_id: int) -> int:
        inserted = 0
        for (sub_id, question_id), row in list(self.answer_states.items()):
            if sub_id != submission_id:
                continue
            key = (submission_id, question_id)
            if key in self.sealed_answers:
                continue
            self.sealed_answers[key] = {
                "submission_seal_id": submission_seal_id,
                "exam_submission_id": submission_id,
                "generated_exam_question_id": question_id,
                "answer_text": row.get("answer_text"),
                "answer_payload_json": row.get("answer_payload_json"),
                "answer_hash": row.get("answer_hash"),
                "answer_length": row.get("answer_length"),
            }
            inserted += 1
        return inserted

    def mark_sealed_file_assets(self, *, submission_id: int, submission_seal_id: int) -> int:
        _ = (submission_id, submission_seal_id)
        return 0

    def update_submission_after_seal(
        self,
        *,
        submission_id: int,
        submission_status: str,
        seal_reason: str,
    ) -> None:
        submission = self.submissions[submission_id]
        submission["submission_status"] = submission_status
        submission["seal_reason"] = seal_reason
        submission["sealed_at"] = datetime.now(timezone.utc)
        if submission["submitted_at"] is None:
            submission["submitted_at"] = datetime.now(timezone.utc)

    def get_seal_summary(self, submission_id: int) -> dict | None:
        seal = self.seals.get(submission_id)
        if seal is None:
            return None
        sealed_count = sum(1 for (sub_id, _question_id) in self.sealed_answers if sub_id == submission_id)
        return {
            "submission_seal_id": seal["submission_seal_id"],
            "exam_submission_id": submission_id,
            "submission_status": self.submissions[submission_id]["submission_status"],
            "seal_status": seal["seal_status"],
            "seal_reason": seal["seal_reason"],
            "sealed_at": seal["sealed_at"],
            "answer_count": int(seal["answer_count"]),
            "submission_hash": seal.get("submission_hash"),
            "sealed_answer_count": sealed_count,
        }

    def list_submission_question_seal_requirements(self, submission_id: int) -> list[dict]:
        _ = submission_id
        return list(self.seal_requirements_rows)

    def insert_submission_history(
        self,
        *,
        exam_submission_id: int,
        exam_session_id: int | None,
        actor_user_id: int | None,
        actor_role: str,
        action_type: str,
        from_status: str | None,
        to_status: str,
        reason_code: str | None,
        note: str | None,
        context_json: dict | None,
        idempotency_key: str | None,
    ) -> dict:
        row = {
            "submission_history_id": len(self.submission_history) + 1,
            "exam_submission_id": exam_submission_id,
            "exam_session_id": exam_session_id,
            "actor_user_id": actor_user_id,
            "actor_role": actor_role,
            "action_type": action_type,
            "from_status": from_status,
            "to_status": to_status,
            "reason_code": reason_code,
            "note": note,
            "context_json": context_json,
            "idempotency_key": idempotency_key,
            "changed_at": datetime.now(timezone.utc),
        }
        self.submission_history.append(row)
        return row


class SnapshotTransactionManager:
    def __init__(self, *targets: object) -> None:
        self.targets = targets
        self._depth = 0
        self._snapshots: list[dict] | None = None

    @contextmanager
    def scope(self):
        is_outer = self._depth == 0
        if is_outer:
            self._snapshots = [deepcopy(target.__dict__) for target in self.targets]

        self._depth += 1
        try:
            yield
        except Exception:
            if is_outer and self._snapshots is not None:
                for target, snapshot in zip(self.targets, self._snapshots):
                    target.__dict__.clear()
                    target.__dict__.update(snapshot)
            raise
        finally:
            self._depth -= 1
            if is_outer:
                self._snapshots = None


class FailingSealSnapshotRepository(InMemorySubmissionRepository):
    def create_sealed_answers_from_state(self, *, submission_id: int, submission_seal_id: int) -> int:
        _ = submission_id
        _ = submission_seal_id
        raise RuntimeError("simulated_sealed_answer_failure")


class MismatchedSealSnapshotRepository(InMemorySubmissionRepository):
    def create_sealed_answers_from_state(self, *, submission_id: int, submission_seal_id: int) -> int:
        _ = submission_id
        _ = submission_seal_id
        return 0


class StubDispatchReadinessService:
    def evaluate_submission(self, *, submission_id: int) -> dict:
        return {
            "submission_id": int(submission_id),
            "is_sealed": True,
            "dispatch_ready": False,
            "dispatch_route": "MANUAL_REVIEW_REQUIRED",
            "capture_required": True,
            "grading_required": True,
            "blockers": ["MISSING_CAPTURE_PROFILE"],
            "modality": "HYBRID",
            "exam_version_id": 5001,
            "capture_profile_id": None,
            "grading_profile_id": 9001,
            "grading_profile_summary": {
                "question_grading_profile_id": 9001,
                "input_source": "DATABASE_SNAPSHOT",
                "requires_capture": True,
                "required_capture_type": "DATABASE",
                "capture_profile_code": None,
                "grading_engine_code": "ENGINE_SQL",
                "comparison_method": "EXACT_MATCH",
            },
        }


class StubCaptureOnlyDispatchReadinessService:
    def evaluate_submission(self, *, submission_id: int) -> dict:
        return {
            "submission_id": int(submission_id),
            "is_sealed": True,
            "dispatch_ready": True,
            "dispatch_route": "CAPTURE_THEN_GRADING",
            "capture_required": True,
            "grading_required": True,
            "blockers": [],
            "modality": "STUDENT_DATABASE",
            "exam_version_id": 5001,
            "capture_profile_id": 44,
            "grading_profile_id": 9002,
            "grading_profile_summary": {
                "question_grading_profile_id": 9002,
                "input_source": "STUDENT_DATABASE_CAPTURE",
                "requires_capture": True,
                "required_capture_type": "POSTGRES_DATABASE_SNAPSHOT",
                "capture_profile_code": "CP_DB",
                "grading_engine_code": "ENGINE_SQL",
                "comparison_method": "EXACT_RESULT_SET",
            },
        }


def _student_user() -> dict:
    return {"user_id": 10, "roles": ["STUDENT"]}


def _proctor_user() -> dict:
    return {"user_id": 20, "roles": ["PROCTOR"]}


def test_autosave_creates_and_updates_answer_state_with_ack_revision() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    first = service.autosave_answers(
        submission_id=1,
        payload={
            "idempotency_key": "batch-1",
            "client_sequence_no": 1,
            "client_saved_at": datetime.now(timezone.utc),
            "client_revision": 1,
            "device_id": None,
            "station_id": None,
            "metadata_json": None,
            "answers": [
                {
                    "generated_exam_question_id": 101,
                    "answer_type": "SQL_TEXT",
                    "answer_text": "SELECT 1",
                    "answer_payload_json": None,
                    "answer_hash": "a" * 64,
                    "answer_length": 8,
                    "client_revision": 1,
                    "metadata_json": None,
                }
            ],
        },
        current_user=_student_user(),
    )
    assert first["batch_status"] == "APPLIED"
    assert first["server_ack_revision"] == 1

    second = service.autosave_answers(
        submission_id=1,
        payload={
            "idempotency_key": "batch-2",
            "client_sequence_no": 2,
            "client_saved_at": datetime.now(timezone.utc),
            "client_revision": 2,
            "device_id": None,
            "station_id": None,
            "metadata_json": None,
            "answers": [
                {
                    "generated_exam_question_id": 101,
                    "answer_type": "SQL_TEXT",
                    "answer_text": "SELECT 2",
                    "answer_payload_json": None,
                    "answer_hash": "b" * 64,
                    "answer_length": 8,
                    "client_revision": 2,
                    "metadata_json": None,
                }
            ],
        },
        current_user=_student_user(),
    )

    assert second["batch_status"] == "APPLIED"
    assert second["server_ack_revision"] == 2
    state = repo.answer_states[(1, 101)]
    assert state["answer_text"] == "SELECT 2"
    assert int(state["server_version"]) == 2


def test_autosave_multiple_choice_maps_generated_option_to_original_option_id() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    result = service.autosave_answers(
        submission_id=1,
        payload={
            "idempotency_key": "batch-mcq-1",
            "client_sequence_no": 1,
            "client_saved_at": datetime.now(timezone.utc),
            "client_revision": 1,
            "device_id": None,
            "station_id": None,
            "metadata_json": None,
            "answers": [
                {
                    "generated_exam_question_id": 202,
                    "answer_type": "MCQ_OPTION",
                    "answer_text": None,
                    "answer_payload_json": {"selected_generated_exam_option_id": 1002},
                    "answer_hash": None,
                    "answer_length": 1,
                    "client_revision": 1,
                    "metadata_json": None,
                }
            ],
        },
        current_user=_student_user(),
    )

    assert result["batch_status"] == "APPLIED"
    state = repo.answer_states[(1, 202)]
    assert state["answer_type"] == "MCQ_OPTION"
    assert state["answer_payload_json"] == {
        "selected_generated_exam_option_id": 1002,
        "selected_original_option_id": 2,
    }


def test_autosave_multiple_choice_rejects_option_from_another_question() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    result = service.autosave_answers(
        submission_id=1,
        payload={
            "idempotency_key": "batch-mcq-invalid-1",
            "client_sequence_no": 1,
            "client_saved_at": datetime.now(timezone.utc),
            "client_revision": 1,
            "device_id": None,
            "station_id": None,
            "metadata_json": None,
            "answers": [
                {
                    "generated_exam_question_id": 202,
                    "answer_type": "MCQ_OPTION",
                    "answer_text": None,
                    "answer_payload_json": {"selected_generated_exam_option_id": 9999},
                    "answer_hash": None,
                    "answer_length": 1,
                    "client_revision": 1,
                    "metadata_json": None,
                }
            ],
        },
        current_user=_student_user(),
    )

    assert result["batch_status"] == "REJECTED"
    assert result["items"][0]["error_code"] == "invalid_generated_option_selection"
    assert (1, 202) not in repo.answer_states


def test_get_answer_state_hides_internal_original_option_mapping() -> None:
    repo = InMemorySubmissionRepository()
    repo.answer_states[(1, 202)] = {
        "answer_state_id": 1,
        "exam_submission_id": 1,
        "generated_exam_question_id": 202,
        "answer_type": "MCQ_OPTION",
        "answer_text": None,
        "answer_payload_json": {
            "selected_generated_exam_option_id": 1003,
            "selected_original_option_id": 3,
        },
        "answer_hash": None,
        "answer_length": 1,
        "client_version": 1,
        "server_version": 1,
        "client_saved_at": datetime.now(timezone.utc),
        "last_saved_at": datetime.now(timezone.utc),
        "answer_status": "DRAFT",
    }
    service = SubmissionService(repository=repo)

    payload = service.get_answer_state(submission_id=1, current_user=_student_user())

    assert payload["items"][0]["answer_payload_json"] == {"selected_generated_exam_option_id": 1003}


def test_seal_creates_sealed_answer_and_is_idempotent() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    service.autosave_answers(
        submission_id=1,
        payload={
            "idempotency_key": "batch-1",
            "client_sequence_no": 1,
            "client_saved_at": datetime.now(timezone.utc),
            "client_revision": 1,
            "device_id": None,
            "station_id": None,
            "metadata_json": None,
            "answers": [
                {
                    "generated_exam_question_id": 101,
                    "answer_type": "SQL_TEXT",
                    "answer_text": "SELECT 1",
                    "answer_payload_json": None,
                    "answer_hash": "a" * 64,
                    "answer_length": 8,
                    "client_revision": 1,
                    "metadata_json": None,
                }
            ],
        },
        current_user=_student_user(),
    )

    first_seal = service.seal_submission(
        submission_id=1,
        payload={
            "seal_idempotency_key": "seal-1",
            "seal_reason": "STUDENT_SUBMIT",
            "metadata_json": None,
        },
        current_user=_student_user(),
    )
    assert first_seal["idempotent"] is False
    assert first_seal["seal_contract_version"] == "S2W-1.3"
    assert first_seal["seal_status"] == "SEALED"
    assert first_seal["seal_outcome"] == "CREATED"
    assert first_seal["sealed_answer_count"] == 1
    assert first_seal["dispatch_ready"] is True
    assert first_seal["dispatch_blockers"] == []
    assert first_seal["dispatch"]["ready"] is True
    assert first_seal["dispatch"]["guard"]["code"] == "submission_not_sealed"

    second_seal = service.seal_submission(
        submission_id=1,
        payload={
            "seal_idempotency_key": "seal-2",
            "seal_reason": "STUDENT_SUBMIT",
            "metadata_json": None,
        },
        current_user=_student_user(),
    )
    assert second_seal["idempotent"] is True
    assert second_seal["seal_status"] == "ALREADY_SEALED"
    assert second_seal["seal_outcome"] == "ALREADY_SEALED"
    assert second_seal["sealed_answer_count"] == 1


def test_autosave_after_seal_does_not_change_sealed_answer() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    service.autosave_answers(
        submission_id=1,
        payload={
            "idempotency_key": "batch-1",
            "client_sequence_no": 1,
            "client_saved_at": datetime.now(timezone.utc),
            "client_revision": 1,
            "device_id": None,
            "station_id": None,
            "metadata_json": None,
            "answers": [
                {
                    "generated_exam_question_id": 101,
                    "answer_type": "SQL_TEXT",
                    "answer_text": "SELECT 1",
                    "answer_payload_json": None,
                    "answer_hash": "a" * 64,
                    "answer_length": 8,
                    "client_revision": 1,
                    "metadata_json": None,
                }
            ],
        },
        current_user=_student_user(),
    )
    service.seal_submission(
        submission_id=1,
        payload={
            "seal_idempotency_key": "seal-1",
            "seal_reason": "STUDENT_SUBMIT",
            "metadata_json": None,
        },
        current_user=_student_user(),
    )

    old_text = repo.sealed_answers[(1, 101)]["answer_text"]

    late_save = service.autosave_answers(
        submission_id=1,
        payload={
            "idempotency_key": "batch-late",
            "client_sequence_no": 3,
            "client_saved_at": datetime.now(timezone.utc),
            "client_revision": 3,
            "device_id": None,
            "station_id": None,
            "metadata_json": None,
            "answers": [
                {
                    "generated_exam_question_id": 101,
                    "answer_type": "SQL_TEXT",
                    "answer_text": "SELECT 999",
                    "answer_payload_json": None,
                    "answer_hash": "c" * 64,
                    "answer_length": 10,
                    "client_revision": 3,
                    "metadata_json": None,
                }
            ],
        },
        current_user=_student_user(),
    )

    assert late_save["batch_status"] == "IGNORED_AFTER_SEAL"
    assert repo.sealed_answers[(1, 101)]["answer_text"] == old_text


def test_seal_rolls_back_all_changes_when_snapshot_insert_fails() -> None:
    repo = FailingSealSnapshotRepository()
    tx = SnapshotTransactionManager(repo)
    service = SubmissionService(repository=repo, transaction_scope=tx.scope)

    service.autosave_answers(
        submission_id=1,
        payload={
            "idempotency_key": "batch-1",
            "client_sequence_no": 1,
            "client_saved_at": datetime.now(timezone.utc),
            "client_revision": 1,
            "device_id": None,
            "station_id": None,
            "metadata_json": None,
            "answers": [
                {
                    "generated_exam_question_id": 101,
                    "answer_type": "SQL_TEXT",
                    "answer_text": "SELECT 1",
                    "answer_payload_json": None,
                    "answer_hash": "a" * 64,
                    "answer_length": 8,
                    "client_revision": 1,
                    "metadata_json": None,
                }
            ],
        },
        current_user=_student_user(),
    )

    with pytest.raises(RuntimeError):
        service.seal_submission(
            submission_id=1,
            payload={
                "seal_idempotency_key": "seal-rollback-1",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
            current_user=_student_user(),
        )

    submission = repo.submissions[1]
    assert repo.get_seal_by_submission_id(1) is None
    assert submission["seal_reason"] is None
    assert submission["sealed_at"] is None
    assert submission["submission_status"] == "IN_PROGRESS"


def test_unauthorized_student_cannot_access_other_submission() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    with pytest.raises(ApiError) as exc:
        service.get_answer_state(
            submission_id=1,
            current_user={"user_id": 11, "roles": ["STUDENT"]},
        )

    assert exc.value.code == "permission_denied"


def test_seal_rejects_blank_idempotency_key() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    with pytest.raises(ApiError) as exc:
        service.seal_submission(
            submission_id=1,
            payload={
                "seal_idempotency_key": "   ",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
            current_user=_student_user(),
        )

    assert exc.value.code == "invalid_seal_idempotency_key"


def test_seal_normalizes_reason_alias_and_status_contract() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    sealed = service.seal_submission(
        submission_id=1,
        payload={
            "seal_idempotency_key": "seal-force-1",
            "seal_reason": "PROCTOR_COLLECT",
            "metadata_json": None,
        },
        current_user=_proctor_user(),
    )

    assert sealed["seal_reason"] == "PROCTOR_COLLECT"
    assert sealed["submission_status"] == "FORCE_SEALED"
    assert sealed["dispatch"]["target"]["exam_submission_id"] == 1
    assert sealed["dispatch"]["ready"] is False
    assert "NO_SEALED_ANSWERS" in sealed["dispatch"]["dispatch_blockers"]


def test_get_seal_preflight_reports_missing_required_text_answer() -> None:
    repo = InMemorySubmissionRepository()
    repo.seal_requirements_rows = [
        {
            "generated_exam_question_id": 101,
            "question_order": 1,
            "question_type": "ESSAY",
            "rendered_question_payload_json": {"answer_ui": {"required": True}},
            "input_source": "SEALED_TEXT_ANSWER",
            "answer_language": "TEXT",
            "requires_capture": False,
            "required_capture_type": None,
            "grading_profile_metadata_json": {},
            "answer_state_id": None,
            "answer_type": None,
            "answer_text": None,
            "answer_payload_json": None,
            "answer_file_asset_id": None,
            "asset_status": None,
            "asset_submission_id": None,
            "asset_question_id": None,
        }
    ]
    service = SubmissionService(repository=repo)

    payload = service.get_seal_preflight(submission_id=1, current_user=_student_user())

    assert payload["can_seal"] is False
    assert payload["counts"]["required_questions"] == 1
    assert any(item["code"] == "REQUIRED_TEXT_MISSING" for item in payload["blockers"])


def test_seal_rejects_missing_required_text_answer() -> None:
    repo = InMemorySubmissionRepository()
    repo.seal_requirements_rows = [
        {
            "generated_exam_question_id": 101,
            "question_order": 1,
            "question_type": "ESSAY",
            "rendered_question_payload_json": {"answer_ui": {"required": True}},
            "input_source": "SEALED_TEXT_ANSWER",
            "answer_language": "TEXT",
            "requires_capture": False,
            "required_capture_type": None,
            "grading_profile_metadata_json": {},
            "answer_state_id": None,
            "answer_type": None,
            "answer_text": None,
            "answer_payload_json": None,
            "answer_file_asset_id": None,
            "asset_status": None,
            "asset_submission_id": None,
            "asset_question_id": None,
        }
    ]
    service = SubmissionService(repository=repo)

    with pytest.raises(ApiError) as exc:
        service.seal_submission(
            submission_id=1,
            payload={
                "seal_idempotency_key": "seal-missing-text-1",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
            current_user=_student_user(),
        )

    assert exc.value.code == "REQUIRED_TEXT_ANSWER_MISSING"


def test_get_seal_preflight_blocks_required_unsupported_input_source() -> None:
    repo = InMemorySubmissionRepository()
    repo.seal_requirements_rows = [
        {
            "generated_exam_question_id": 111,
            "question_order": 1,
            "question_type": "ESSAY",
            "rendered_question_payload_json": {"answer_ui": {"required": True}},
            "input_source": "UNKNOWN_SOURCE",
            "answer_language": "TEXT",
            "requires_capture": False,
            "required_capture_type": None,
            "grading_profile_metadata_json": {},
            "answer_state_id": None,
            "answer_type": None,
            "answer_text": None,
            "answer_payload_json": None,
            "answer_file_asset_id": None,
            "asset_status": None,
            "asset_submission_id": None,
            "asset_question_id": None,
        }
    ]
    service = SubmissionService(repository=repo)

    payload = service.get_seal_preflight(submission_id=1, current_user=_student_user())

    assert payload["can_seal"] is False
    assert payload["counts"]["required_questions"] == 1
    assert any(
        item["code"] == "UNSUPPORTED_INPUT_SOURCE"
        and item["generated_exam_question_id"] == 111
        and item["details"]["input_source"] == "UNKNOWN_SOURCE"
        for item in payload["blockers"]
    )


def test_seal_rejects_required_unsupported_input_source_without_creating_sealed_answers() -> None:
    repo = InMemorySubmissionRepository()
    repo.seal_requirements_rows = [
        {
            "generated_exam_question_id": 112,
            "question_order": 1,
            "question_type": "ESSAY",
            "rendered_question_payload_json": {"answer_ui": {"required": True}},
            "input_source": "UNKNOWN_SOURCE",
            "answer_language": "TEXT",
            "requires_capture": False,
            "required_capture_type": None,
            "grading_profile_metadata_json": {},
            "answer_state_id": None,
            "answer_type": None,
            "answer_text": None,
            "answer_payload_json": None,
            "answer_file_asset_id": None,
            "asset_status": None,
            "asset_submission_id": None,
            "asset_question_id": None,
        }
    ]
    service = SubmissionService(repository=repo)

    with pytest.raises(ApiError) as exc:
        service.seal_submission(
            submission_id=1,
            payload={
                "seal_idempotency_key": "seal-unsupported-input-1",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
            current_user=_student_user(),
        )

    assert exc.value.code == "UNSUPPORTED_INPUT_SOURCE"
    assert repo.get_seal_by_submission_id(1) is None
    assert repo.sealed_answers == {}


def test_optional_unsupported_input_source_is_warning_and_remains_unsealed() -> None:
    repo = InMemorySubmissionRepository()
    repo.seal_requirements_rows = [
        {
            "generated_exam_question_id": 113,
            "question_order": 1,
            "question_type": "ESSAY",
            "rendered_question_payload_json": {"answer_ui": {"required": False}},
            "input_source": "UNKNOWN_SOURCE",
            "answer_language": "TEXT",
            "requires_capture": False,
            "required_capture_type": None,
            "grading_profile_metadata_json": {"required": False},
            "answer_state_id": None,
            "answer_type": None,
            "answer_text": None,
            "answer_payload_json": None,
            "answer_file_asset_id": None,
            "asset_status": None,
            "asset_submission_id": None,
            "asset_question_id": None,
        }
    ]
    service = SubmissionService(repository=repo)

    payload = service.get_seal_preflight(submission_id=1, current_user=_student_user())
    sealed = service.seal_submission(
        submission_id=1,
        payload={
            "seal_idempotency_key": "seal-unsupported-optional-1",
            "seal_reason": "STUDENT_SUBMIT",
            "metadata_json": None,
        },
        current_user=_student_user(),
    )

    assert payload["can_seal"] is True
    assert any(
        item["code"] == "UNSUPPORTED_INPUT_SOURCE"
        and item["severity"] == "warning"
        and item["generated_exam_question_id"] == 113
        for item in payload["warnings"]
    )
    assert sealed["seal_status"] in {"SEALED", "ALREADY_SEALED"}
    assert (1, 113) not in repo.sealed_answers


def test_assigned_room_proctor_can_force_seal_submission() -> None:
    repo = InMemorySubmissionRepository()
    repo.proctor_assignments[(300, 20)] = "ASSIGNED"
    service = SubmissionService(repository=repo)

    sealed = service.seal_submission(
        submission_id=1,
        payload={
            "seal_idempotency_key": "seal-force-assigned-1",
            "seal_reason": "PROCTOR_COLLECT",
            "metadata_json": None,
        },
        current_user=_proctor_user(),
    )

    assert sealed["submission_status"] == "FORCE_SEALED"
    assert sealed["seal_reason"] == "PROCTOR_COLLECT"


def test_confirmed_room_proctor_can_force_seal_submission() -> None:
    repo = InMemorySubmissionRepository()
    repo.proctor_assignments[(300, 20)] = "CONFIRMED"
    service = SubmissionService(repository=repo)

    sealed = service.seal_submission(
        submission_id=1,
        payload={
            "seal_idempotency_key": "seal-force-confirmed-1",
            "seal_reason": "PROCTOR_COLLECT",
            "metadata_json": None,
        },
        current_user=_proctor_user(),
    )

    assert sealed["submission_status"] == "FORCE_SEALED"
    assert sealed["seal_reason"] == "PROCTOR_COLLECT"


def test_student_cannot_use_internal_time_expired_reason() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    with pytest.raises(ApiError) as exc:
        service.seal_submission(
            submission_id=1,
            payload={
                "seal_idempotency_key": "seal-time-expired-1",
                "seal_reason": "TIME_EXPIRED",
                "metadata_json": None,
            },
            current_user=_student_user(),
        )

    assert exc.value.code == "permission_denied"


def test_student_submit_is_blocked_when_room_is_closed() -> None:
    repo = InMemorySubmissionRepository()
    repo.submissions[1]["room_status"] = "CLOSED"
    service = SubmissionService(repository=repo)

    with pytest.raises(ApiError) as exc:
        service.seal_submission(
            submission_id=1,
            payload={
                "seal_idempotency_key": "seal-room-closed-1",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
            current_user=_student_user(),
        )

    assert exc.value.code == "exam_sitting_room_closed"
    assert repo.submission_history == []


def test_unassigned_proctor_cannot_access_submission() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    with pytest.raises(ApiError) as exc:
        service.get_answer_state(
            submission_id=1,
            current_user={"user_id": 21, "roles": ["PROCTOR"]},
        )

    assert exc.value.code == "permission_denied"


def test_wrong_room_proctor_cannot_force_seal_submission() -> None:
    repo = InMemorySubmissionRepository()
    repo.proctor_assignments.pop((300, 20), None)
    repo.proctor_assignments[(301, 20)] = "ASSIGNED"
    service = SubmissionService(repository=repo)

    with pytest.raises(ApiError) as exc:
        service.seal_submission(
            submission_id=1,
            payload={
                "seal_idempotency_key": "seal-force-wrong-room-1",
                "seal_reason": "PROCTOR_COLLECT",
                "metadata_json": None,
            },
            current_user=_proctor_user(),
        )

    assert exc.value.code == "permission_denied"


def test_cancelled_room_proctor_cannot_force_seal_submission() -> None:
    repo = InMemorySubmissionRepository()
    repo.proctor_assignments[(300, 20)] = "CANCELLED"
    service = SubmissionService(repository=repo)

    with pytest.raises(ApiError) as exc:
        service.seal_submission(
            submission_id=1,
            payload={
                "seal_idempotency_key": "seal-force-cancelled-1",
                "seal_reason": "PROCTOR_COLLECT",
                "metadata_json": None,
            },
            current_user=_proctor_user(),
        )

    assert exc.value.code == "permission_denied"


def test_student_submit_expired_window_returns_api_error_with_datetime_detail() -> None:
    repo = InMemorySubmissionRepository()
    repo.submissions[1]["deadline_at"] = datetime.now(timezone.utc)
    service = SubmissionService(repository=repo)

    with pytest.raises(ApiError) as exc:
        service.seal_submission(
            submission_id=1,
            payload={
                "seal_idempotency_key": "seal-expired-window-1",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
            current_user=_student_user(),
        )

    assert exc.value.code == "submission_window_expired"
    assert isinstance(exc.value.details["deadline_at"], datetime)


def test_successful_seal_writes_sanitized_submission_history() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    service.seal_submission(
        submission_id=1,
        payload={
            "seal_idempotency_key": "seal-history-1",
            "seal_reason": "STUDENT_SUBMIT",
            "note": "submit now",
            "metadata_json": {
                "source": "candidate_ui",
                "client_request_id": "req-123",
                "password": "should-not-persist",
                "nested": {"token": "hidden"},
            },
        },
        current_user=_student_user(),
    )

    assert len(repo.submission_history) == 1
    history = repo.submission_history[0]
    assert history["actor_role"] == "STUDENT"
    assert history["action_type"] == "SUBMITTED"
    assert history["from_status"] == "DRAFT"
    assert history["to_status"] == "SUBMITTED"
    assert history["reason_code"] == "STUDENT_SUBMIT"
    assert history["note"] == "submit now"
    assert history["context_json"] == {"source": "candidate_ui", "client_request_id": "req-123"}


def test_seal_rollback_removes_history_when_snapshot_fails() -> None:
    repo = FailingSealSnapshotRepository()
    tx = SnapshotTransactionManager(repo)
    service = SubmissionService(repository=repo, transaction_scope=tx.scope)

    with pytest.raises(RuntimeError):
        service.seal_submission(
            submission_id=1,
            payload={
                "seal_idempotency_key": "seal-history-rollback-1",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": {"source": "candidate_ui"},
            },
            current_user=_student_user(),
        )

    assert repo.submission_history == []


def test_seal_rejects_when_existing_non_active_seal_exists() -> None:
    repo = InMemorySubmissionRepository()
    repo.seals[1] = {
        "submission_seal_id": 44,
        "exam_submission_id": 1,
        "seal_idempotency_key": "old",
        "seal_status": "FAILED",
        "seal_reason": "SYSTEM_RECOVERY_SEAL",
        "sealed_at": datetime.now(timezone.utc),
        "sealed_by": 20,
        "answer_count": 0,
        "submission_hash": None,
    }
    service = SubmissionService(repository=repo)

    with pytest.raises(ApiError) as exc:
        service.seal_submission(
            submission_id=1,
            payload={
                "seal_idempotency_key": "seal-new",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
            current_user=_student_user(),
        )

    assert exc.value.code == "submission_seal_already_exists"
    assert exc.value.details["seal_status"] == "FAILED"


def test_seal_rolls_back_when_snapshot_count_mismatch() -> None:
    repo = MismatchedSealSnapshotRepository()
    tx = SnapshotTransactionManager(repo)
    service = SubmissionService(repository=repo, transaction_scope=tx.scope)

    service.autosave_answers(
        submission_id=1,
        payload={
            "idempotency_key": "batch-1",
            "client_sequence_no": 1,
            "client_saved_at": datetime.now(timezone.utc),
            "client_revision": 1,
            "device_id": None,
            "station_id": None,
            "metadata_json": None,
            "answers": [
                {
                    "generated_exam_question_id": 101,
                    "answer_type": "SQL_TEXT",
                    "answer_text": "SELECT 1",
                    "answer_payload_json": None,
                    "answer_hash": "a" * 64,
                    "answer_length": 8,
                    "client_revision": 1,
                    "metadata_json": None,
                }
            ],
        },
        current_user=_student_user(),
    )

    with pytest.raises(ApiError) as exc:
        service.seal_submission(
            submission_id=1,
            payload={
                "seal_idempotency_key": "seal-mismatch-1",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
            current_user=_student_user(),
        )

    assert exc.value.code == "sealed_answer_snapshot_mismatch"
    assert repo.get_seal_by_submission_id(1) is None


def test_get_seal_status_returns_dispatch_contract() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    service.seal_submission(
        submission_id=1,
        payload={
            "seal_idempotency_key": "seal-status-1",
            "seal_reason": "STUDENT_SUBMIT",
            "metadata_json": None,
        },
        current_user=_student_user(),
    )

    status_payload = service.get_seal_status(submission_id=1, current_user=_student_user())

    assert status_payload["seal_contract_version"] == "S2W-1.3"
    assert status_payload["dispatch"]["ready"] is False
    assert "NO_SEALED_ANSWERS" in status_payload["dispatch"]["dispatch_blockers"]
    assert status_payload["dispatch"]["guard"]["required_seal_status"] == "SEALED"


def test_seal_response_includes_dispatch_route_from_readiness_service() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(
        repository=repo,
        dispatch_readiness_service=StubDispatchReadinessService(),
    )

    service.autosave_answers(
        submission_id=1,
        payload={
            "idempotency_key": "batch-dispatch-1",
            "client_sequence_no": 1,
            "client_saved_at": datetime.now(timezone.utc),
            "client_revision": 1,
            "device_id": None,
            "station_id": None,
            "metadata_json": None,
            "answers": [
                {
                    "generated_exam_question_id": 101,
                    "answer_type": "SQL_TEXT",
                    "answer_text": "SELECT 1",
                    "answer_payload_json": None,
                    "answer_hash": "a" * 64,
                    "answer_length": 8,
                    "client_revision": 1,
                    "metadata_json": None,
                }
            ],
        },
        current_user=_student_user(),
    )

    sealed = service.seal_submission(
        submission_id=1,
        payload={
            "seal_idempotency_key": "seal-dispatch-1",
            "seal_reason": "STUDENT_SUBMIT",
            "metadata_json": None,
        },
        current_user=_student_user(),
    )

    assert sealed["dispatch_ready"] is False
    assert sealed["dispatch_route"] == "MANUAL_REVIEW_REQUIRED"
    assert sealed["dispatch_blockers"] == ["MISSING_CAPTURE_PROFILE"]
    assert sealed["dispatch"]["dispatch_route"] == "MANUAL_REVIEW_REQUIRED"
    assert sealed["dispatch"]["capture_required"] is True
    assert sealed["dispatch"]["grading_profile_id"] == 9001


def test_seal_rejects_invalid_reason() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    with pytest.raises(ApiError) as exc:
        service.seal_submission(
            submission_id=1,
            payload={
                "seal_idempotency_key": "seal-invalid-reason-1",
                "seal_reason": "NOT_A_REASON",
                "metadata_json": None,
            },
            current_user=_student_user(),
        )

    assert exc.value.code == "invalid_seal_reason"


def test_seal_zero_answers_is_allowed_with_dispatch_blocker() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    sealed = service.seal_submission(
        submission_id=1,
        payload={
            "seal_idempotency_key": "seal-zero-answer-1",
            "seal_reason": "STUDENT_SUBMIT",
            "metadata_json": None,
        },
        current_user=_student_user(),
    )

    assert sealed["sealed_answer_count"] == 0
    assert sealed["dispatch_ready"] is False
    assert "NO_SEALED_ANSWERS" in sealed["dispatch_blockers"]
    assert "NO_SEALED_ANSWERS" in sealed["dispatch"]["dispatch_blockers"]


def test_capture_only_seal_zero_answers_uses_profile_aware_readiness() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(
        repository=repo,
        dispatch_readiness_service=StubCaptureOnlyDispatchReadinessService(),
    )

    sealed = service.seal_submission(
        submission_id=1,
        payload={
            "seal_idempotency_key": "seal-capture-only-1",
            "seal_reason": "STUDENT_SUBMIT",
            "metadata_json": None,
        },
        current_user=_student_user(),
    )

    assert sealed["sealed_answer_count"] == 0
    assert sealed["dispatch_ready"] is True
    assert sealed["dispatch_route"] == "CAPTURE_THEN_GRADING"
    assert sealed["dispatch_blockers"] == []
    assert sealed["dispatch"]["ready"] is True
    assert sealed["dispatch"]["dispatch_blockers"] == []
    assert sealed["dispatch"]["next_action"] == "DISPATCH_PENDING"


def test_unauthorized_student_cannot_seal_other_submission() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    with pytest.raises(ApiError) as exc:
        service.seal_submission(
            submission_id=1,
            payload={
                "seal_idempotency_key": "seal-unauthorized-1",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
            current_user={"user_id": 11, "roles": ["STUDENT"]},
        )

    assert exc.value.code == "permission_denied"


def test_required_file_upload_question_without_file_cannot_seal() -> None:
    repo = InMemorySubmissionRepository()
    repo.seal_requirements_rows = [
        {
            "generated_exam_question_id": 201,
            "rendered_question_payload_json": {"answer_ui": {"required": True}},
            "input_source": "SEALED_FILE_REF",
            "grading_profile_metadata_json": {"required": True},
            "answer_type": None,
            "answer_payload_json": None,
            "answer_file_asset_id": None,
            "asset_status": None,
            "asset_submission_id": None,
            "asset_question_id": None,
        }
    ]
    service = SubmissionService(repository=repo)
    with pytest.raises(ApiError) as exc:
        service.seal_submission(
            submission_id=1,
            payload={"seal_idempotency_key": "seal-file-missing-1", "seal_reason": "STUDENT_SUBMIT", "metadata_json": None},
            current_user=_student_user(),
        )
    assert exc.value.code == "REQUIRED_FILE_ANSWER_MISSING"
    assert exc.value.details["generated_exam_question_id"] == 201


def test_required_file_upload_question_with_file_can_seal_and_preserve_file_ref() -> None:
    repo = InMemorySubmissionRepository()
    repo.answer_states[(1, 202)] = {
        "answer_state_id": 1,
        "exam_submission_id": 1,
        "generated_exam_question_id": 202,
        "answer_type": "FILE_REF",
        "answer_text": None,
        "answer_payload_json": {"file_asset_id": 9901, "original_filename": "bai_lam.zip"},
        "answer_hash": "a" * 64,
        "answer_length": 100,
        "client_version": 1,
        "server_version": 1,
        "client_saved_at": datetime.now(timezone.utc),
        "last_saved_at": datetime.now(timezone.utc),
        "answer_status": "DRAFT",
    }
    repo.seal_requirements_rows = [
        {
            "generated_exam_question_id": 202,
            "rendered_question_payload_json": {"answer_ui": {"required": True}},
            "input_source": "SEALED_FILE_REF",
            "grading_profile_metadata_json": {"required": True},
            "answer_type": "FILE_REF",
            "answer_payload_json": {"file_asset_id": 9901, "original_filename": "bai_lam.zip"},
            "answer_file_asset_id": 9901,
            "asset_status": "ACTIVE",
            "asset_submission_id": 1,
            "asset_question_id": 202,
        }
    ]
    service = SubmissionService(repository=repo)
    sealed = service.seal_submission(
        submission_id=1,
        payload={"seal_idempotency_key": "seal-file-ok-1", "seal_reason": "STUDENT_SUBMIT", "metadata_json": None},
        current_user=_student_user(),
    )
    assert sealed["seal_status"] in {"SEALED", "ALREADY_SEALED"}
    assert repo.sealed_answers[(1, 202)]["answer_payload_json"]["file_asset_id"] == 9901


def test_optional_file_upload_question_without_file_can_seal() -> None:
    repo = InMemorySubmissionRepository()
    repo.seal_requirements_rows = [
        {
            "generated_exam_question_id": 203,
            "rendered_question_payload_json": {"answer_ui": {"required": False}},
            "input_source": "SEALED_FILE_REF",
            "grading_profile_metadata_json": {"required": False},
            "answer_type": None,
            "answer_payload_json": None,
            "answer_file_asset_id": None,
            "asset_status": None,
            "asset_submission_id": None,
            "asset_question_id": None,
        }
    ]
    service = SubmissionService(repository=repo)
    sealed = service.seal_submission(
        submission_id=1,
        payload={"seal_idempotency_key": "seal-file-optional-1", "seal_reason": "STUDENT_SUBMIT", "metadata_json": None},
        current_user=_student_user(),
    )
    assert sealed["idempotent"] is False
