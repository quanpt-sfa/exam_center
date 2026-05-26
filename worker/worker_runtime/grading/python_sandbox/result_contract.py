"""Result contracts for local/dev-only Python sandbox proof."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


STATUS_PASSED = "PASSED"
STATUS_FAILED = "FAILED"
STATUS_SYNTAX_ERROR = "SYNTAX_ERROR"
STATUS_RUNTIME_ERROR = "RUNTIME_ERROR"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_MEMORY_LIMIT_EXCEEDED = "MEMORY_LIMIT_EXCEEDED"
STATUS_OUTPUT_LIMIT_EXCEEDED = "OUTPUT_LIMIT_EXCEEDED"
STATUS_POLICY_VIOLATION = "POLICY_VIOLATION"
STATUS_RUNTIME_UNAVAILABLE = "RUNTIME_UNAVAILABLE"
STATUS_INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"

TEST_STATUS_PASSED = "PASSED"
TEST_STATUS_FAILED = "FAILED"
TEST_STATUS_ERROR = "ERROR"
TEST_STATUS_SKIPPED = "SKIPPED"


@dataclass(frozen=True, slots=True)
class TestCaseResult:
    """Per-test-case execution result."""

    test_case_id: str
    visibility: str
    status: str
    score_fraction: float
    error_summary: str | None
    stdout_preview: str | None


TestCaseResult.__test__ = False


@dataclass(frozen=True, slots=True)
class PythonSandboxRunResult:
    """Top-level sandbox run result."""

    status: str
    test_results: tuple[TestCaseResult, ...]
    stdout_preview: str | None
    stderr_preview: str | None
    error_summary: str | None
    runtime_ms: int
    memory_peak_mb: float | None
    policy_violation_code: str | None
    runner_version: str
    sanitized_metadata: dict[str, Any]


PythonSandboxRunResult.__test__ = False
