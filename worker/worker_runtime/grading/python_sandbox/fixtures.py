"""Built-in local fixtures for Python sandbox proof CLI."""

from __future__ import annotations

from worker_runtime.grading.python_sandbox.runner_contract import PythonSandboxRunRequest
from worker_runtime.grading.python_sandbox.runner_contract import PythonSandboxTestCase
from worker_runtime.grading.python_sandbox.sandbox_policy import PythonSandboxPolicy


def build_fixture_request(fixture_name: str) -> PythonSandboxRunRequest:
    fixture = str(fixture_name or "correct").strip().lower()
    policy = PythonSandboxPolicy()

    fixtures: dict[str, PythonSandboxRunRequest] = {
        "correct": PythonSandboxRunRequest(
            source_code="def solve(values):\n    return sum(values)\n",
            entrypoint_mode="FUNCTION_SOLVE",
            function_name="solve",
            test_cases=(
                PythonSandboxTestCase(
                    test_case_id="public-1",
                    visibility="PUBLIC",
                    input_payload_json={"args": [[1, 2, 3]], "kwargs": {}},
                    expected_output_json=6,
                ),
                PythonSandboxTestCase(
                    test_case_id="hidden-1",
                    visibility="HIDDEN",
                    input_payload_json={"args": [[5, 5]], "kwargs": {}},
                    expected_output_json=10,
                ),
            ),
            timeout_seconds=2,
            memory_limit_mb=64,
            output_limit_bytes=512,
            runtime_version="PYTHON_3_11",
            policy=policy,
        ),
        "wrong-output": PythonSandboxRunRequest(
            source_code="def solve(values):\n    return 0\n",
            entrypoint_mode="FUNCTION_SOLVE",
            function_name="solve",
            test_cases=(
                PythonSandboxTestCase(
                    test_case_id="public-1",
                    visibility="PUBLIC",
                    input_payload_json={"args": [[1, 2, 3]], "kwargs": {}},
                    expected_output_json=6,
                ),
            ),
            timeout_seconds=2,
            memory_limit_mb=64,
            output_limit_bytes=512,
            runtime_version="PYTHON_3_11",
            policy=policy,
        ),
        "syntax-error": PythonSandboxRunRequest(
            source_code="def solve(values):\nreturn sum(values)\n",
            entrypoint_mode="FUNCTION_SOLVE",
            function_name="solve",
            test_cases=(
                PythonSandboxTestCase(
                    test_case_id="public-1",
                    visibility="PUBLIC",
                    input_payload_json={"args": [[1]], "kwargs": {}},
                    expected_output_json=1,
                ),
            ),
            timeout_seconds=2,
            memory_limit_mb=64,
            output_limit_bytes=512,
            runtime_version="PYTHON_3_11",
            policy=policy,
        ),
        "runtime-error": PythonSandboxRunRequest(
            source_code="def solve(values):\n    raise RuntimeError('boom secret=123')\n",
            entrypoint_mode="FUNCTION_SOLVE",
            function_name="solve",
            test_cases=(
                PythonSandboxTestCase(
                    test_case_id="public-1",
                    visibility="PUBLIC",
                    input_payload_json={"args": [[1]], "kwargs": {}},
                    expected_output_json=1,
                ),
            ),
            timeout_seconds=2,
            memory_limit_mb=64,
            output_limit_bytes=512,
            runtime_version="PYTHON_3_11",
            policy=policy,
        ),
        "timeout": PythonSandboxRunRequest(
            source_code="def solve(values):\n    while True:\n        pass\n",
            entrypoint_mode="FUNCTION_SOLVE",
            function_name="solve",
            test_cases=(
                PythonSandboxTestCase(
                    test_case_id="public-1",
                    visibility="PUBLIC",
                    input_payload_json={"args": [[1]], "kwargs": {}},
                    expected_output_json=1,
                ),
            ),
            timeout_seconds=1,
            memory_limit_mb=64,
            output_limit_bytes=512,
            runtime_version="PYTHON_3_11",
            policy=policy,
        ),
        "stdout-flood": PythonSandboxRunRequest(
            source_code="def solve(values):\n    print('x' * 10000)\n    return len(values)\n",
            entrypoint_mode="FUNCTION_SOLVE",
            function_name="solve",
            test_cases=(
                PythonSandboxTestCase(
                    test_case_id="public-1",
                    visibility="PUBLIC",
                    input_payload_json={"args": [[1, 2, 3]], "kwargs": {}},
                    expected_output_json=3,
                ),
            ),
            timeout_seconds=2,
            memory_limit_mb=64,
            output_limit_bytes=256,
            runtime_version="PYTHON_3_11",
            policy=policy,
        ),
        "forbidden-import": PythonSandboxRunRequest(
            source_code="import socket\n\ndef solve(values):\n    return len(values)\n",
            entrypoint_mode="FUNCTION_SOLVE",
            function_name="solve",
            test_cases=(
                PythonSandboxTestCase(
                    test_case_id="public-1",
                    visibility="PUBLIC",
                    input_payload_json={"args": [[1, 2]], "kwargs": {}},
                    expected_output_json=2,
                ),
            ),
            timeout_seconds=2,
            memory_limit_mb=64,
            output_limit_bytes=256,
            runtime_version="PYTHON_3_11",
            policy=policy,
        ),
    }

    if fixture not in fixtures:
        raise ValueError(f"Unsupported python sandbox fixture: {fixture}")
    return fixtures[fixture]
