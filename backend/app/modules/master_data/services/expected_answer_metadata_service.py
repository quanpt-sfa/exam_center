"""Metadata-safe helper service for delivery.generated_expected_answer."""

from __future__ import annotations

from app.modules.master_data.repositories.expected_answer_metadata_repository import ExpectedAnswerMetadataRepository


class ExpectedAnswerMetadataService:
    """Provides metadata-level checks without exposing expected-answer payload content."""

    def __init__(
        self,
        *,
        expected_answer_metadata_repository: ExpectedAnswerMetadataRepository | None = None,
    ) -> None:
        self._expected_answer_metadata_repository = (
            expected_answer_metadata_repository or ExpectedAnswerMetadataRepository()
        )

    def is_supported(self, *, conn: object | None = None) -> bool:
        return self._expected_answer_metadata_repository.table_exists(conn=conn)

    def get_exam_version_metadata_summary(self, *, exam_version_id: int, conn: object | None = None) -> dict:
        if not self.is_supported(conn=conn):
            return {
                "supported": False,
                "exam_version_id": int(exam_version_id),
                "expected_answer_count": 0,
                "with_metadata_count": 0,
            }

        expected_answer_count = self._expected_answer_metadata_repository.count_for_exam_version(
            int(exam_version_id),
            conn=conn,
        )
        with_metadata_count = self._expected_answer_metadata_repository.count_with_metadata_for_exam_version(
            int(exam_version_id),
            conn=conn,
        )

        return {
            "supported": True,
            "exam_version_id": int(exam_version_id),
            "expected_answer_count": int(expected_answer_count),
            "with_metadata_count": int(with_metadata_count),
        }


def build_expected_answer_metadata_service() -> ExpectedAnswerMetadataService:
    """FastAPI dependency factory for expected answer metadata service."""

    return ExpectedAnswerMetadataService()
