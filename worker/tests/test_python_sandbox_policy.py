"""Policy and sanitization tests for Python sandbox proof."""

from __future__ import annotations

from pathlib import Path
import sys

WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.python_sandbox.result_contract import PythonSandboxRunResult
from worker_runtime.grading.python_sandbox.result_contract import TestCaseResult
from worker_runtime.grading.python_sandbox.runner_contract import PythonSandboxRunRequest
from worker_runtime.grading.python_sandbox.runner_contract import PythonSandboxTestCase
from worker_runtime.grading.python_sandbox.sandbox_policy import PythonSandboxPolicy
from worker_runtime.grading.python_sandbox.sandbox_policy import detect_forbidden_source_indicator
from worker_runtime.grading.python_sandbox.sandbox_policy import validate_run_request
from worker_runtime.grading.python_sandbox.sanitizer import sanitize_error_summary
from worker_runtime.grading.python_sandbox.sanitizer import to_student_safe_result


def _request(*, source_code: str, visibility: str = "PUBLIC") -> PythonSandboxRunRequest:
    return PythonSandboxRunRequest(
        source_code=source_code,
        entrypoint_mode="FUNCTION_SOLVE",
        function_name="solve",
        test_cases=(
            PythonSandboxTestCase(
                test_case_id="case-1",
                visibility=visibility,
                input_payload_json={"args": [[1, 2, 3]], "kwargs": {}},
                expected_output_json=6,
            ),
        ),
        timeout_seconds=2,
        memory_limit_mb=64,
        output_limit_bytes=256,
        runtime_version="PYTHON_3_11",
        policy=PythonSandboxPolicy(),
    )


def test_policy_rejects_oversized_source() -> None:
    request = _request(source_code="x" * 20_000)

    is_valid, code, message = validate_run_request(request)

    assert is_valid is False
    assert code == "source_too_large"
    assert "size limit" in str(message)


def test_policy_detects_forbidden_import_indicator() -> None:
    indicator = detect_forbidden_source_indicator("import socket\n", policy=PythonSandboxPolicy())

    assert indicator is not None
    assert indicator[0] == "forbidden_import"


def test_sanitizer_removes_traceback_and_paths() -> None:
    sanitized = sanitize_error_summary(
        "Traceback (most recent call last):\n  File \"/tmp/root_entrypoint.py\", line 7, in <module>\nValueError: boom"
    )

    assert sanitized == "ValueError: boom"


def test_student_safe_result_redacts_hidden_case_details() -> None:
    result = PythonSandboxRunResult(
        status="FAILED",
        test_results=(
            TestCaseResult(
                test_case_id="hidden-1",
                visibility="HIDDEN",
                status="FAILED",
                score_fraction=0.0,
                error_summary="expected 10 but got 9",
                stdout_preview="secret stdout",
            ),
        ),
        stdout_preview="top-level",
        stderr_preview="stderr",
        error_summary="boom",
        runtime_ms=15,
        memory_peak_mb=None,
        policy_violation_code=None,
        runner_version="test",
        sanitized_metadata={},
    )

    redacted = to_student_safe_result(result)

    assert redacted.test_results[0].error_summary == "Hidden test failed."
    assert redacted.test_results[0].stdout_preview is None
