"""OpenAPI contract snapshot guard for processing-status endpoint (ACF-5)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.main import app


PATH = "/api/v1/submissions/{exam_submission_id}/processing-status"
METHOD = "get"
REPO_ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT_PATH = REPO_ROOT / "docs" / "api" / "openapi_submission_processing_status_snapshot.json"

REQUIRED_PUBLIC_FIELDS = [
    "exam_submission_id",
    "overall_status",
    "is_terminal",
    "can_retry",
    "pending_reason",
    "failure_reason",
    "seal",
    "capture",
    "grading",
    "tasks",
    "results",
    "score",
    "timestamps",
]

FORBIDDEN_TOKENS = [
    "answer_state",
    "answer_text",
    "sealed_answer_text",
    "raw_answer",
    "row_payload_json",
    "capture_dataset_row",
]


def _operation() -> dict[str, Any]:
    schema = app.openapi()
    assert PATH in schema.get("paths", {})
    path_item = schema["paths"][PATH]
    assert METHOD in path_item
    return path_item[METHOD]


def _json_content(response_spec: dict[str, Any]) -> dict[str, Any]:
    return response_spec.get("content", {}).get("application/json", {})


def _normalize_operation(operation: dict[str, Any]) -> dict[str, Any]:
    parameters = operation.get("parameters", [])
    exam_param = None
    for param in parameters:
        if param.get("name") == "exam_submission_id":
            exam_param = {
                "name": param.get("name"),
                "in": param.get("in"),
                "required": bool(param.get("required")),
                "schema": {
                    "type": param.get("schema", {}).get("type"),
                    "exclusiveMinimum": param.get("schema", {}).get("exclusiveMinimum"),
                },
            }
            break

    responses = operation.get("responses", {})
    success_schema = _json_content(responses.get("200", {})).get("schema", {})
    success_required_fields = (
        success_schema.get("properties", {}).get("data", {}).get("required", [])
        if isinstance(success_schema, dict)
        else []
    )

    normalized_responses: dict[str, dict[str, Any]] = {}
    for code in sorted(responses.keys()):
        normalized_responses[code] = {
            "description": responses[code].get("description"),
        }

    return {
        "path": PATH,
        "method": METHOD.upper(),
        "parameter": exam_param,
        "response_codes": sorted(responses.keys()),
        "success_required_fields": success_required_fields,
        "responses": normalized_responses,
    }


def test_processing_status_openapi_contract_guard() -> None:
    operation = _operation()

    parameters = operation.get("parameters", [])
    exam_param = next((p for p in parameters if p.get("name") == "exam_submission_id"), None)
    assert exam_param is not None
    assert exam_param.get("in") == "path"
    assert exam_param.get("required") is True

    responses = operation.get("responses", {})
    assert {"200", "403", "404", "503"}.issubset(responses.keys())
    assert "400" in responses or "422" in responses

    success_schema = _json_content(responses["200"]).get("schema", {})
    success_data_required = success_schema.get("properties", {}).get("data", {}).get("required", [])
    for field in REQUIRED_PUBLIC_FIELDS:
        assert field in success_data_required

    rendered = json.dumps(operation, sort_keys=True).lower()
    for token in FORBIDDEN_TOKENS:
        assert token not in rendered


def test_processing_status_openapi_snapshot_is_stable() -> None:
    assert SNAPSHOT_PATH.exists(), f"Missing snapshot file: {SNAPSHOT_PATH}"

    operation = _operation()
    normalized = _normalize_operation(operation)

    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert normalized == expected
