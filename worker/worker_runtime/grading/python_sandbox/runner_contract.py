"""Input contracts for local/dev-only Python sandbox proof."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Protocol

from worker_runtime.grading.python_sandbox.result_contract import PythonSandboxRunResult
from worker_runtime.grading.python_sandbox.sandbox_policy import PythonSandboxPolicy


@dataclass(frozen=True, slots=True)
class PythonSandboxTestCase:
    """Single Python sandbox test case."""

    test_case_id: str
    visibility: str
    input_payload_json: Any
    expected_output_json: Any
    comparison_mode: str = "EXACT_JSON"
    score_weight: float = 1.0
    hidden_feedback: str | None = None


@dataclass(frozen=True, slots=True)
class PythonSandboxRunRequest:
    """Request contract for a sandboxed Python function run."""

    source_code: str
    entrypoint_mode: str
    function_name: str
    test_cases: tuple[PythonSandboxTestCase, ...]
    timeout_seconds: int
    memory_limit_mb: int
    output_limit_bytes: int
    runtime_version: str
    policy: PythonSandboxPolicy


class PythonSandboxRunner(Protocol):
    """Contract for a Python sandbox proof runner."""

    def run(self, request: PythonSandboxRunRequest) -> PythonSandboxRunResult:
        ...