"""Policy validation for local/dev-only Python sandbox proof."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


_DEFAULT_FORBIDDEN_MODULES = (
    "asyncio",
    "builtins",
    "ctypes",
    "ensurepip",
    "ftplib",
    "http",
    "importlib",
    "inspect",
    "multiprocessing",
    "os",
    "pathlib",
    "pip",
    "psycopg",
    "resource",
    "select",
    "shutil",
    "signal",
    "socket",
    "sqlite3",
    "subprocess",
    "sys",
    "telnetlib",
    "tempfile",
    "threading",
    "urllib",
    "venv",
)

_DEFAULT_ALLOWED_MODULES = (
    "collections",
    "decimal",
    "fractions",
    "functools",
    "heapq",
    "itertools",
    "json",
    "math",
    "operator",
    "random",
    "re",
    "statistics",
    "string",
)


@dataclass(frozen=True, slots=True)
class PythonSandboxPolicy:
    """Sandbox policy limits and defense-in-depth indicators."""

    max_source_bytes: int = 16_384
    max_test_cases: int = 32
    max_total_input_bytes: int = 32_768
    max_output_bytes: int = 4_096
    max_hidden_test_cases: int = 16
    forbidden_modules: tuple[str, ...] = _DEFAULT_FORBIDDEN_MODULES
    allowed_modules: tuple[str, ...] = _DEFAULT_ALLOWED_MODULES
    redact_hidden_case_details: bool = True


def validate_run_request(request: Any) -> tuple[bool, str | None, str | None]:
    """Validate request shape and cheap policy preconditions."""

    source_code = str(getattr(request, "source_code", "") or "")
    policy = getattr(request, "policy", None)
    if policy is None:
        return False, "policy_missing", "Sandbox policy is required."

    if len(source_code.encode("utf-8")) > int(policy.max_source_bytes):
        return False, "source_too_large", "Source code exceeds sandbox source size limit."

    test_cases = tuple(getattr(request, "test_cases", ()) or ())
    if not test_cases:
        return False, "test_cases_missing", "At least one test case is required."
    if len(test_cases) > int(policy.max_test_cases):
        return False, "too_many_test_cases", "Sandbox request exceeds max test case count."

    hidden_count = 0
    total_input_bytes = 0
    for test_case in test_cases:
        if str(getattr(test_case, "visibility", "")).strip().upper() == "HIDDEN":
            hidden_count += 1
        total_input_bytes += _json_like_size(getattr(test_case, "input_payload_json", None))
        total_input_bytes += _json_like_size(getattr(test_case, "expected_output_json", None))

    if hidden_count > int(policy.max_hidden_test_cases):
        return False, "too_many_hidden_test_cases", "Sandbox request exceeds hidden test case limit."
    if total_input_bytes > int(policy.max_total_input_bytes):
        return False, "test_payload_too_large", "Sandbox request payload exceeds byte budget."

    indicator = detect_forbidden_source_indicator(source_code, policy=policy)
    if indicator is not None:
        return False, indicator[0], indicator[1]

    return True, None, None


def detect_forbidden_source_indicator(source_code: str, *, policy: PythonSandboxPolicy) -> tuple[str, str] | None:
    """Cheap defense-in-depth scan for obviously disallowed modules and APIs."""

    text = str(source_code or "")
    for module_name in policy.forbidden_modules:
        pattern = rf"(^|\n)\s*(import|from)\s+{re.escape(module_name)}\b"
        if re.search(pattern, text, flags=re.IGNORECASE):
            return (
                "forbidden_import",
                f"Sandbox source uses forbidden module '{module_name}'.",
            )

    forbidden_calls = {
        "__import__(": "forbidden_dynamic_import",
        "open(": "forbidden_filesystem_access",
        "socket.": "forbidden_network_access",
        "subprocess.": "forbidden_subprocess_access",
        "os.system(": "forbidden_process_spawn",
        "eval(": "forbidden_eval",
        "exec(": "forbidden_exec",
    }
    lowered = text.lower()
    for token, code in forbidden_calls.items():
        if token.lower() in lowered:
            return code, f"Sandbox source uses forbidden API token '{token.strip()}'."

    return None


def _json_like_size(value: Any) -> int:
    if value is None:
        return 4
    if isinstance(value, (bool, int, float)):
        return len(str(value))
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    if isinstance(value, dict):
        return sum(_json_like_size(key) + _json_like_size(raw) for key, raw in value.items())
    if isinstance(value, (list, tuple, set)):
        return sum(_json_like_size(item) for item in value)
    return len(repr(value).encode("utf-8"))
