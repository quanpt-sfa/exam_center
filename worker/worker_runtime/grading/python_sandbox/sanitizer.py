"""Sanitization helpers for Python sandbox proof outputs."""

from __future__ import annotations

from dataclasses import replace
import re

from worker_runtime.grading.python_sandbox.result_contract import PythonSandboxRunResult
from worker_runtime.grading.python_sandbox.result_contract import TestCaseResult
from worker_runtime.runtime_logging import sanitize_log_value


def sanitize_preview(text: str | None, *, limit: int) -> str | None:
    if text is None:
        return None
    sanitized = str(sanitize_log_value(str(text or ""))).replace("\r\n", "\n")
    sanitized = re.sub(r"(?i)(secret|token|api[_-]?key)\s*[:=]\s*[^,;\s]+", r"\1=<redacted>", sanitized)
    sanitized = re.sub(r"File \"[^\"]+\"", 'File "<redacted>"', sanitized)
    sanitized = re.sub(r"line \d+", "line <redacted>", sanitized)
    if "Traceback (most recent call last):" in sanitized:
        lines = [line for line in sanitized.splitlines() if line.strip()]
        sanitized = lines[-1] if lines else "Execution failed."
    sanitized = sanitized.splitlines()[0] if "\n" in sanitized else sanitized
    sanitized = sanitized.strip()
    if len(sanitized.encode("utf-8")) > int(limit):
        encoded = sanitized.encode("utf-8")[: int(limit)]
        sanitized = encoded.decode("utf-8", errors="ignore").rstrip() + "..."
    return sanitized or None


def sanitize_error_summary(text: str | None) -> str | None:
    return sanitize_preview(text, limit=240)


def to_student_safe_result(result: PythonSandboxRunResult) -> PythonSandboxRunResult:
    """Redact hidden-case details before any student-facing exposure."""

    redacted_results: list[TestCaseResult] = []
    for item in result.test_results:
        if str(item.visibility).strip().upper() == "HIDDEN":
            redacted_results.append(
                replace(
                    item,
                    error_summary=("Hidden test failed." if item.status != "PASSED" else None),
                    stdout_preview=None,
                )
            )
            continue
        redacted_results.append(
            replace(
                item,
                error_summary=sanitize_error_summary(item.error_summary),
                stdout_preview=sanitize_preview(item.stdout_preview, limit=160),
            )
        )

    return replace(
        result,
        test_results=tuple(redacted_results),
        stdout_preview=sanitize_preview(result.stdout_preview, limit=160),
        stderr_preview=sanitize_preview(result.stderr_preview, limit=160),
        error_summary=sanitize_error_summary(result.error_summary),
    )
