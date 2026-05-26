"""Runner contract tests for local/dev-only Python sandbox proof."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.python_sandbox.fixtures import build_fixture_request
from worker_runtime.grading.python_sandbox.local_docker_runner import LocalDockerPythonSandboxRunner


def _completed(payload: dict, *, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["docker"],
        returncode=returncode,
        stdout=json.dumps(payload),
        stderr=stderr,
    )


def test_docker_unavailable_refuses_unsafe_host_fallback() -> None:
    runner = LocalDockerPythonSandboxRunner(docker_binary="")

    result = runner.run(build_fixture_request("correct"))

    assert result.status == "RUNTIME_UNAVAILABLE"
    assert result.sanitized_metadata["host_fallback_allowed"] is False


def test_correct_function_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = LocalDockerPythonSandboxRunner(docker_binary="docker")
    monkeypatch.setattr(
        runner,
        "_invoke_docker",
        lambda **kwargs: _completed(
            {
                "status": "PASSED",
                "test_results": [
                    {
                        "test_case_id": "public-1",
                        "visibility": "PUBLIC",
                        "status": "PASSED",
                        "score_fraction": 1.0,
                        "error_summary": None,
                        "stdout_preview": None,
                    },
                    {
                        "test_case_id": "hidden-1",
                        "visibility": "HIDDEN",
                        "status": "PASSED",
                        "score_fraction": 1.0,
                        "error_summary": None,
                        "stdout_preview": None,
                    },
                ],
                "stdout_preview": None,
                "stderr_preview": None,
                "error_summary": None,
                "runtime_ms": 12,
                "memory_peak_mb": 20.5,
                "policy_violation_code": None,
                "sanitized_metadata": {},
            }
        ),
    )

    result = runner.run(build_fixture_request("correct"))

    assert result.status == "PASSED"
    assert len(result.test_results) == 2
    assert result.test_results[1].stdout_preview is None


def test_wrong_output_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = LocalDockerPythonSandboxRunner(docker_binary="docker")
    monkeypatch.setattr(
        runner,
        "_invoke_docker",
        lambda **kwargs: _completed(
            {
                "status": "FAILED",
                "test_results": [
                    {
                        "test_case_id": "public-1",
                        "visibility": "PUBLIC",
                        "status": "FAILED",
                        "score_fraction": 0.0,
                        "error_summary": "expected 6 got 0",
                        "stdout_preview": None,
                    }
                ],
                "error_summary": "Output mismatch",
                "runtime_ms": 9,
                "sanitized_metadata": {},
            }
        ),
    )

    result = runner.run(build_fixture_request("wrong-output"))

    assert result.status == "FAILED"
    assert result.test_results[0].status == "FAILED"


@pytest.mark.parametrize(
    ("fixture_name", "status", "error_summary"),
    [
        ("syntax-error", "SYNTAX_ERROR", "SyntaxError: invalid syntax"),
        ("runtime-error", "RUNTIME_ERROR", "RuntimeError: boom secret=123"),
        ("timeout", "TIMEOUT", "Execution exceeded timeout limit."),
        ("stdout-flood", "OUTPUT_LIMIT_EXCEEDED", None),
        ("correct", "MEMORY_LIMIT_EXCEEDED", "Memory limit exceeded."),
    ],
)
def test_runner_maps_controlled_statuses(
    monkeypatch: pytest.MonkeyPatch,
    fixture_name: str,
    status: str,
    error_summary: str | None,
) -> None:
    runner = LocalDockerPythonSandboxRunner(docker_binary="docker")
    monkeypatch.setattr(
        runner,
        "_invoke_docker",
        lambda **kwargs: _completed(
            {
                "status": status,
                "test_results": [],
                "stdout_preview": "x" * 500,
                "stderr_preview": None,
                "error_summary": error_summary,
                "runtime_ms": 11,
                "sanitized_metadata": {"output_truncated": status == "OUTPUT_LIMIT_EXCEEDED"},
            }
        ),
    )

    result = runner.run(build_fixture_request(fixture_name))

    assert result.status == status
    if status == "RUNTIME_ERROR":
        assert "secret=123" not in str(result.error_summary)


def test_policy_violation_blocks_forbidden_import_before_execution() -> None:
    runner = LocalDockerPythonSandboxRunner(docker_binary="docker")

    result = runner.run(build_fixture_request("forbidden-import"))

    assert result.status == "POLICY_VIOLATION"
    assert result.policy_violation_code == "forbidden_import"


def test_runner_does_not_pass_host_env_secrets_to_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = LocalDockerPythonSandboxRunner(docker_binary="docker")
    observed: dict[str, object] = {}

    def _fake_run(command, **kwargs):
        observed["command"] = command
        observed["env"] = kwargs.get("env")
        return _completed(
            {
                "status": "PASSED",
                "test_results": [],
                "runtime_ms": 5,
                "sanitized_metadata": {},
            }
        )

    monkeypatch.setattr("subprocess.run", _fake_run)

    result = runner.run(build_fixture_request("correct"))

    assert result.status == "PASSED"
    assert observed["env"] == {}


def test_hidden_test_output_is_redacted_in_student_safe_result(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = LocalDockerPythonSandboxRunner(docker_binary="docker")
    monkeypatch.setattr(
        runner,
        "_invoke_docker",
        lambda **kwargs: _completed(
            {
                "status": "FAILED",
                "test_results": [
                    {
                        "test_case_id": "hidden-1",
                        "visibility": "HIDDEN",
                        "status": "FAILED",
                        "score_fraction": 0.0,
                        "error_summary": "expected 10 got 9",
                        "stdout_preview": "secret detail",
                    }
                ],
                "runtime_ms": 7,
                "sanitized_metadata": {},
            }
        ),
    )

    result = runner.run(build_fixture_request("correct"))

    assert result.test_results[0].error_summary == "Hidden test failed."
    assert result.test_results[0].stdout_preview is None


def test_cleanup_occurs_after_run(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = LocalDockerPythonSandboxRunner(docker_binary="docker")
    cleaned: dict[str, object] = {"workspace": None}

    monkeypatch.setattr(runner, "_create_workspace", lambda: "temp-workspace")
    monkeypatch.setattr(
        runner,
        "_cleanup_workspace",
        lambda workspace: cleaned.update({"workspace": workspace}) or True,
    )
    monkeypatch.setattr(
        runner,
        "_invoke_docker",
        lambda **kwargs: _completed(
            {
                "status": "PASSED",
                "test_results": [],
                "runtime_ms": 4,
                "sanitized_metadata": {},
            }
        ),
    )

    result = runner.run(build_fixture_request("correct"))

    assert result.status == "PASSED"
    assert cleaned["workspace"] == "temp-workspace"
