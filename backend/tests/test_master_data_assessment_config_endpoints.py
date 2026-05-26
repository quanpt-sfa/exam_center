"""Endpoint permission tests for MD-5 assessment configuration routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.permissions import PermissionDeniedError
from app.main import app
from app.modules.master_data.common.permissions import require_master_data_publish


client = TestClient(app)


def test_exam_version_publish_rejects_without_publish_permission() -> None:
    def _deny_publish() -> dict:
        raise PermissionDeniedError("Missing required permission: master_data:publish")

    app.dependency_overrides[require_master_data_publish] = _deny_publish

    try:
        response = client.post("/api/v1/master-data/exam-versions/1/publish")

        assert response.status_code == 403
        payload = response.json()
        assert payload["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()
