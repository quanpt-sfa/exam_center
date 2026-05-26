from __future__ import annotations
import pytest
from app.modules.delivery.services.delivery_service import DeliveryService


class _CandidatePhotoContractRepo:
    def __init__(self, candidate_profile: dict | None) -> None:
        self.candidate_profile = candidate_profile

    def get_session_by_id(self, session_id: int) -> dict:
        return {
            "exam_session_id": session_id,
            "exam_assignment_id": 200,
            "exam_sitting_id": 1,
            "student_id": 1001,
            "session_code": "S-900",
            "session_no": 1,
            "session_status": "IN_PROGRESS",
            "time_limit_seconds": 3600,
            "extra_time_seconds": 0,
            "started_at": None,
            "deadline_at": None,
            "ended_at": None,
            "last_seen_at": None,
            "last_activity_at": None,
            "generated_exam_instance_id": 7001,
            "generation_status": "GENERATED",
        }

    def get_student_id_by_user_id(self, user_id: int) -> int:
        return 1001

    def list_generated_paper_questions(self, session_id: int) -> list:
        return [{
            "generated_exam_question_id": 1,
            "question_order": 1,
            "question_code": "Q1",
            "question_type": "SINGLE_CHOICE",
            "rendered_question_text": "Question 1 text",
            "rendered_question_payload_json": "{}",
            "score": 1.0,
        }]

    def get_or_create_submission_for_session(self, session_id: int, actor_user_id: int | None) -> dict:
        return {
            "exam_submission_id": 12001,
            "exam_session_id": session_id,
            "generated_exam_instance_id": 7001,
            "submission_status": "DRAFT",
            "opened_at": None,
            "first_saved_at": None,
            "last_saved_at": None,
            "submitted_at": None,
            "sealed_at": None,
        }

    def get_student_candidate_profile(self, student_id: int) -> dict | None:
        return self.candidate_profile

    def list_active_paper_assets_for_session(self, session_id: int) -> list:
        return []


def _student_user() -> dict:
    return {"user_id": 10, "roles": ["STUDENT"]}


def test_exam_taking_payload_candidate_photo_url_from_https_ref() -> None:
    # 1. If photo_ref is a browser-loadable HTTPS/HTTP URL
    profile = {
        "student_id": 1001,
        "student_code": "B22DCCN999",
        "full_name": "Test Student Name",
        "photo_ref": "https://assets.local/mock-photo.jpg",
    }
    repo = _CandidatePhotoContractRepo(profile)
    service = DeliveryService(repository=repo)
    
    payload = service.get_exam_taking_payload(session_id=99, current_user=_student_user())
    
    assert payload["candidate"] is not None
    assert payload["candidate"]["full_name"] == "Test Student Name"
    assert payload["candidate"]["student_code"] == "B22DCCN999"
    assert payload["candidate"]["photo_ref"] == "https://assets.local/mock-photo.jpg"
    assert payload["candidate"]["photo_url"] == "https://assets.local/mock-photo.jpg"


def test_exam_taking_payload_candidate_internal_photo_ref_does_not_become_photo_url() -> None:
    # 2. If photo_ref is an internal/unresolved reference (not http/https)
    internal_refs = [
        "photos/student-001.jpg",
        "s3://bucket/student-001.jpg",
        "photo://student-001",
        "internal-storage-key-123",
    ]
    for ref in internal_refs:
        profile = {
            "student_id": 1001,
            "student_code": "B22DCCN999",
            "full_name": "Test Student Name",
            "photo_ref": ref,
        }
        repo = _CandidatePhotoContractRepo(profile)
        service = DeliveryService(repository=repo)
        
        payload = service.get_exam_taking_payload(session_id=99, current_user=_student_user())
        
        assert payload["candidate"] is not None
        assert payload["candidate"]["full_name"] == "Test Student Name"
        assert payload["candidate"]["student_code"] == "B22DCCN999"
        assert payload["candidate"]["photo_ref"] == ref
        assert payload["candidate"]["photo_url"] is None


def test_exam_taking_payload_candidate_missing_photo_has_null_photo_url() -> None:
    # 3. If candidate has no photo (photo_ref is None/missing)
    profile = {
        "student_id": 1001,
        "student_code": "B22DCCN999",
        "full_name": "Test Student Name",
        "photo_ref": None,
    }
    repo = _CandidatePhotoContractRepo(profile)
    service = DeliveryService(repository=repo)
    
    payload = service.get_exam_taking_payload(session_id=99, current_user=_student_user())
    
    assert payload["candidate"] is not None
    assert payload["candidate"]["full_name"] == "Test Student Name"
    assert payload["candidate"]["student_code"] == "B22DCCN999"
    assert payload["candidate"]["photo_ref"] is None
    assert payload["candidate"]["photo_url"] is None
