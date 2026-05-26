"""CLI tests for local/dev-only Python sandbox proof."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.cli import main as worker_cli_main
from worker_runtime.grading.python_sandbox.result_contract import PythonSandboxRunResult
from worker_runtime.grading.python_sandbox.result_contract import TestCaseResult


def test_cli_run_python_sandbox_proof_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _FakeRunner:
        def __init__(self, **kwargs):
            _ = kwargs

        def run(self, request):
            assert request.function_name == "solve"
            return PythonSandboxRunResult(
                status="PASSED",
                test_results=(
                    TestCaseResult(
                        test_case_id="public-1",
                        visibility="PUBLIC",
                        status="PASSED",
                        score_fraction=1.0,
                        error_summary=None,
                        stdout_preview=None,
                    ),
                ),
                stdout_preview=None,
                stderr_preview=None,
                error_summary=None,
                runtime_ms=8,
                memory_peak_mb=None,
                policy_violation_code=None,
                runner_version="test-runner",
                sanitized_metadata={"docker_available": True},
            )

    monkeypatch.setattr("worker_runtime.cli.LocalDockerPythonSandboxRunner", _FakeRunner)

    exit_code = worker_cli_main(["run-python-sandbox-proof", "--fixture", "correct"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"status": "PASSED"' in output


def test_cli_run_python_sandbox_proof_returns_non_zero_for_unavailable_runtime(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _FakeRunner:
        def __init__(self, **kwargs):
            _ = kwargs

        def run(self, request):
            _ = request
            return PythonSandboxRunResult(
                status="RUNTIME_UNAVAILABLE",
                test_results=tuple(),
                stdout_preview=None,
                stderr_preview=None,
                error_summary="docker missing",
                runtime_ms=3,
                memory_peak_mb=None,
                policy_violation_code=None,
                runner_version="test-runner",
                sanitized_metadata={"host_fallback_allowed": False},
            )

    monkeypatch.setattr("worker_runtime.cli.LocalDockerPythonSandboxRunner", _FakeRunner)

    exit_code = worker_cli_main(["run-python-sandbox-proof", "--fixture", "correct"])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert '"host_fallback_allowed": false' in output.lower()


def test_cli_run_python_sandbox_proof_uses_builtin_fixtures_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "worker_runtime.cli.load_runtime_settings",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not load runtime settings")),
    )

    class _FakeRunner:
        def __init__(self, **kwargs):
            _ = kwargs

        def run(self, request):
            assert request.function_name == "solve"
            return PythonSandboxRunResult(
                status="PASSED",
                test_results=tuple(),
                stdout_preview=None,
                stderr_preview=None,
                error_summary=None,
                runtime_ms=1,
                memory_peak_mb=None,
                policy_violation_code=None,
                runner_version="test-runner",
                sanitized_metadata={},
            )

    monkeypatch.setattr("worker_runtime.cli.LocalDockerPythonSandboxRunner", _FakeRunner)

    assert worker_cli_main(["run-python-sandbox-proof", "--fixture", "wrong-output"]) == 0
