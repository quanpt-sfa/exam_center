"""Local Docker-backed Python sandbox proof runner with no unsafe host fallback."""

from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from time import perf_counter
from typing import Any

from worker_runtime.grading.python_sandbox.result_contract import PythonSandboxRunResult
from worker_runtime.grading.python_sandbox.result_contract import STATUS_INFRASTRUCTURE_ERROR
from worker_runtime.grading.python_sandbox.result_contract import STATUS_MEMORY_LIMIT_EXCEEDED
from worker_runtime.grading.python_sandbox.result_contract import STATUS_OUTPUT_LIMIT_EXCEEDED
from worker_runtime.grading.python_sandbox.result_contract import STATUS_POLICY_VIOLATION
from worker_runtime.grading.python_sandbox.result_contract import STATUS_RUNTIME_UNAVAILABLE
from worker_runtime.grading.python_sandbox.result_contract import STATUS_TIMEOUT
from worker_runtime.grading.python_sandbox.result_contract import TestCaseResult
from worker_runtime.grading.python_sandbox.runner_contract import PythonSandboxRunRequest
from worker_runtime.grading.python_sandbox.sandbox_policy import validate_run_request
from worker_runtime.grading.python_sandbox.sanitizer import sanitize_error_summary
from worker_runtime.grading.python_sandbox.sanitizer import sanitize_preview
from worker_runtime.grading.python_sandbox.sanitizer import to_student_safe_result


_RUNNER_VERSION = "phase2h-3-local-docker-proof-v1"
_DEFAULT_IMAGE = "python:3.11-alpine"

_HARNESS_SCRIPT = r'''
import builtins
import io
import json
import signal
import sys
import time

try:
    import resource
except Exception:
    resource = None


class PolicyError(RuntimeError):
    pass


class LimitedBuffer(io.StringIO):
    def __init__(self, limit_bytes):
        super().__init__()
        self._limit_bytes = max(1, int(limit_bytes))
        self._bytes_written = 0
        self._truncated = False

    @property
    def truncated(self):
        return self._truncated

    def write(self, text):
        value = str(text)
        encoded = value.encode("utf-8", errors="ignore")
        remaining = self._limit_bytes - self._bytes_written
        if remaining <= 0:
            self._truncated = True
            return 0
        chunk = encoded[:remaining]
        self._bytes_written += len(chunk)
        if len(chunk) < len(encoded):
            self._truncated = True
        return super().write(chunk.decode("utf-8", errors="ignore"))


def _restricted_import_factory(allowed_modules):
    allowed = set(str(item) for item in allowed_modules)

    def _restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
        root = str(name).split(".")[0]
        if root not in allowed:
            raise PolicyError(f"Import of module '{root}' is not allowed.")
        return __import__(name, globals, locals, fromlist, level)

    return _restricted_import


def _build_builtins(allowed_modules):
    allowed_names = {
        "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
        "int", "isinstance", "len", "list", "map", "max", "min", "print",
        "range", "reversed", "round", "set", "sorted", "str", "sum", "tuple",
        "zip", "Exception", "ValueError", "TypeError", "RuntimeError", "AssertionError"
    }
    safe = {name: getattr(builtins, name) for name in allowed_names}
    safe["__import__"] = _restricted_import_factory(allowed_modules)
    return safe


def _normalize_call_input(payload):
    if isinstance(payload, dict) and "args" in payload:
        args = payload.get("args") or []
        kwargs = payload.get("kwargs") or {}
        return list(args), dict(kwargs)
    return [payload], {}


def _compare(actual, expected, mode):
    comparison_mode = str(mode or "EXACT_JSON").upper()
    if comparison_mode == "EXACT_JSON":
        return actual == expected
    if comparison_mode == "NUMERIC_TOLERANCE":
        return abs(float(actual) - float(expected)) <= 1e-6
    if comparison_mode == "STRING_NORMALIZED":
        return str(actual).strip() == str(expected).strip()
    if comparison_mode == "UNORDERED_JSON_ARRAY":
        return sorted(actual) == sorted(expected)
    raise PolicyError(f"Unsupported comparison mode '{comparison_mode}'.")


def _install_limits(memory_limit_mb, timeout_seconds):
    if resource is None:
        return
    memory_bytes = int(memory_limit_mb) * 1024 * 1024
    try:
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    except Exception:
        pass
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (max(1, int(timeout_seconds)), max(1, int(timeout_seconds))))
    except Exception:
        pass


def _disable_network_calls():
    import socket

    def _blocked(*args, **kwargs):
        raise PolicyError("Network access is disabled inside the sandbox.")

    socket.socket = _blocked
    socket.create_connection = _blocked


def main():
    request = json.loads(sys.stdin.read())
    timeout_seconds = max(1, int(request.get("timeout_seconds") or 1))
    output_limit_bytes = max(64, int(request.get("output_limit_bytes") or 256))
    memory_limit_mb = max(16, int(request.get("memory_limit_mb") or 64))
    allowed_modules = tuple(request.get("policy", {}).get("allowed_modules") or [])
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("timeout")))
    signal.alarm(timeout_seconds)
    _install_limits(memory_limit_mb, timeout_seconds)
    _disable_network_calls()
    stdout_buffer = LimitedBuffer(output_limit_bytes)
    stderr_buffer = LimitedBuffer(output_limit_bytes)
    sys.stdout = stdout_buffer
    sys.stderr = stderr_buffer
    started = time.perf_counter()
    builtins_scope = _build_builtins(allowed_modules)
    namespace = {"__builtins__": builtins_scope}
    result = {
        "status": "FAILED",
        "test_results": [],
        "stdout_preview": None,
        "stderr_preview": None,
        "error_summary": None,
        "runtime_ms": 0,
        "memory_peak_mb": None,
        "policy_violation_code": None,
        "sanitized_metadata": {},
    }
    try:
        code = compile(request["source_code"], "sandbox_source.py", "exec")
        exec(code, namespace, namespace)
        fn = namespace.get(request["function_name"])
        if not callable(fn):
            raise RuntimeError("Entrypoint function is not defined.")
        all_passed = True
        for item in request["test_cases"]:
            args, kwargs = _normalize_call_input(item.get("input_payload_json"))
            try:
                actual = fn(*args, **kwargs)
                passed = _compare(actual, item.get("expected_output_json"), item.get("comparison_mode"))
                all_passed = all_passed and bool(passed)
                result["test_results"].append(
                    {
                        "test_case_id": item.get("test_case_id"),
                        "visibility": item.get("visibility"),
                        "status": ("PASSED" if passed else "FAILED"),
                        "score_fraction": (1.0 if passed else 0.0),
                        "error_summary": None if passed else "Output did not match expected result.",
                        "stdout_preview": stdout_buffer.getvalue() or None,
                    }
                )
            except TimeoutError:
                raise
            except MemoryError:
                result["status"] = "MEMORY_LIMIT_EXCEEDED"
                result["error_summary"] = "Memory limit exceeded."
                result["test_results"].append(
                    {
                        "test_case_id": item.get("test_case_id"),
                        "visibility": item.get("visibility"),
                        "status": "ERROR",
                        "score_fraction": 0.0,
                        "error_summary": "Memory limit exceeded.",
                        "stdout_preview": stdout_buffer.getvalue() or None,
                    }
                )
                break
            except PolicyError as exc:
                result["status"] = "POLICY_VIOLATION"
                result["policy_violation_code"] = "policy_runtime_violation"
                result["error_summary"] = str(exc)
                result["test_results"].append(
                    {
                        "test_case_id": item.get("test_case_id"),
                        "visibility": item.get("visibility"),
                        "status": "ERROR",
                        "score_fraction": 0.0,
                        "error_summary": str(exc),
                        "stdout_preview": stdout_buffer.getvalue() or None,
                    }
                )
                break
            except Exception as exc:
                result["status"] = "RUNTIME_ERROR"
                result["error_summary"] = f"{exc.__class__.__name__}: {exc}"
                result["test_results"].append(
                    {
                        "test_case_id": item.get("test_case_id"),
                        "visibility": item.get("visibility"),
                        "status": "ERROR",
                        "score_fraction": 0.0,
                        "error_summary": f"{exc.__class__.__name__}: {exc}",
                        "stdout_preview": stdout_buffer.getvalue() or None,
                    }
                )
                break
        if result["status"] == "FAILED":
            result["status"] = "PASSED" if all_passed else "FAILED"
    except SyntaxError as exc:
        result["status"] = "SYNTAX_ERROR"
        result["error_summary"] = f"SyntaxError: {exc.msg}"
    except TimeoutError:
        result["status"] = "TIMEOUT"
        result["error_summary"] = "Execution exceeded timeout limit."
    except PolicyError as exc:
        result["status"] = "POLICY_VIOLATION"
        result["policy_violation_code"] = "policy_runtime_violation"
        result["error_summary"] = str(exc)
    except MemoryError:
        result["status"] = "MEMORY_LIMIT_EXCEEDED"
        result["error_summary"] = "Memory limit exceeded."
    except Exception as exc:
        result["status"] = "INFRASTRUCTURE_ERROR"
        result["error_summary"] = f"{exc.__class__.__name__}: {exc}"
    finally:
        signal.alarm(0)
        result["runtime_ms"] = int((time.perf_counter() - started) * 1000)
        result["stdout_preview"] = stdout_buffer.getvalue() or None
        result["stderr_preview"] = stderr_buffer.getvalue() or None
        if stdout_buffer.truncated or stderr_buffer.truncated:
            result["sanitized_metadata"]["output_truncated"] = True
            if result["status"] == "PASSED":
                result["status"] = "OUTPUT_LIMIT_EXCEEDED"
        print(json.dumps(result))


if __name__ == "__main__":
    main()
'''


class LocalDockerPythonSandboxRunner:
    """Docker-backed local runner proof that refuses any unsafe host fallback."""

    def __init__(
        self,
        *,
        docker_binary: str | None = None,
        image_name: str | None = None,
        runner_version: str = _RUNNER_VERSION,
    ) -> None:
        self._docker_binary = str(docker_binary).strip() if docker_binary else (shutil.which("docker") or "")
        self._image_name = str(image_name or os.getenv("PYTHON_SANDBOX_DOCKER_IMAGE") or _DEFAULT_IMAGE).strip()
        self._runner_version = str(runner_version)

    def run(self, request: PythonSandboxRunRequest) -> PythonSandboxRunResult:
        started = perf_counter()
        is_valid, violation_code, violation_message = validate_run_request(request)
        if not is_valid:
            return self._result(
                status=STATUS_POLICY_VIOLATION,
                runtime_ms=started,
                error_summary=violation_message,
                policy_violation_code=violation_code,
                sanitized_metadata={"docker_available": bool(self._docker_binary)},
            )

        if not self.is_available():
            return self._result(
                status=STATUS_RUNTIME_UNAVAILABLE,
                runtime_ms=started,
                error_summary="Local Docker runtime is unavailable; unsafe host execution is refused.",
                sanitized_metadata={
                    "docker_available": False,
                    "host_fallback_allowed": False,
                },
            )

        workspace = self._create_workspace()
        try:
            completed = self._invoke_docker(request=request, workspace=workspace)
        except subprocess.TimeoutExpired:
            return self._result(
                status=STATUS_TIMEOUT,
                runtime_ms=started,
                error_summary="Execution exceeded timeout limit.",
                sanitized_metadata={"docker_available": True, "workspace_cleaned": False},
            )
        except Exception as exc:  # noqa: BLE001
            return self._result(
                status=STATUS_INFRASTRUCTURE_ERROR,
                runtime_ms=started,
                error_summary=str(exc),
                sanitized_metadata={"docker_available": True, "workspace_cleaned": False},
            )
        finally:
            workspace_cleaned = self._cleanup_workspace(workspace)

        parsed = self._parse_completed_payload(completed)
        sanitized_metadata = dict(parsed.sanitized_metadata)
        sanitized_metadata["docker_available"] = True
        sanitized_metadata["workspace_cleaned"] = workspace_cleaned
        return to_student_safe_result(
            PythonSandboxRunResult(
                status=parsed.status,
                test_results=parsed.test_results,
                stdout_preview=parsed.stdout_preview,
                stderr_preview=parsed.stderr_preview,
                error_summary=parsed.error_summary,
                runtime_ms=parsed.runtime_ms or int((perf_counter() - started) * 1000),
                memory_peak_mb=parsed.memory_peak_mb,
                policy_violation_code=parsed.policy_violation_code,
                runner_version=self._runner_version,
                sanitized_metadata=sanitized_metadata,
            )
        )

    def is_available(self) -> bool:
        return bool(self._docker_binary)

    def _invoke_docker(self, *, request: PythonSandboxRunRequest, workspace: str) -> subprocess.CompletedProcess[str]:
        command = [
            self._docker_binary,
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--user",
            "65532:65532",
            "--pids-limit",
            "64",
            "--memory",
            f"{int(request.memory_limit_mb)}m",
            "--cpus",
            "1.0",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=16m",
            "--tmpfs",
            "/workspace:rw,nosuid,nodev,size=16m",
            "-w",
            "/workspace",
            self._image_name,
            "python",
            "-I",
            "-S",
            "-c",
            _HARNESS_SCRIPT,
        ]
        payload = json.dumps(self._request_payload(request))
        _ = workspace
        return subprocess.run(
            command,
            input=payload,
            capture_output=True,
            text=True,
            timeout=max(1, int(request.timeout_seconds)) + 2,
            env={},
            cwd=None,
            check=False,
        )

    def _request_payload(self, request: PythonSandboxRunRequest) -> dict[str, Any]:
        payload = asdict(request)
        payload["test_cases"] = [asdict(item) for item in request.test_cases]
        payload["policy"] = asdict(request.policy)
        return payload

    def _parse_completed_payload(self, completed: subprocess.CompletedProcess[str]) -> PythonSandboxRunResult:
        stderr_preview = sanitize_preview(completed.stderr, limit=160)
        stdout_text = str(completed.stdout or "").strip()
        if completed.returncode == 137:
            return self._result(
                status=STATUS_MEMORY_LIMIT_EXCEEDED,
                runtime_ms=0.0,
                error_summary="Sandbox process exceeded memory limit.",
                stderr_preview=stderr_preview,
                sanitized_metadata={"docker_exit_code": completed.returncode},
            )

        try:
            payload = json.loads(stdout_text)
        except json.JSONDecodeError:
            return self._result(
                status=STATUS_INFRASTRUCTURE_ERROR,
                runtime_ms=0.0,
                error_summary=(
                    "Sandbox runner returned a non-JSON payload."
                    if completed.returncode == 0
                    else f"Sandbox runner failed with exit code {completed.returncode}."
                ),
                stdout_preview=sanitize_preview(stdout_text, limit=160),
                stderr_preview=stderr_preview,
                sanitized_metadata={"docker_exit_code": completed.returncode},
            )

        status = str(payload.get("status") or STATUS_INFRASTRUCTURE_ERROR).strip().upper()
        if status == "OUTPUT_LIMIT_EXCEEDED":
            status = STATUS_OUTPUT_LIMIT_EXCEEDED
        test_results = tuple(
            TestCaseResult(
                test_case_id=str(item.get("test_case_id") or ""),
                visibility=str(item.get("visibility") or "PUBLIC"),
                status=str(item.get("status") or "ERROR"),
                score_fraction=float(item.get("score_fraction") or 0.0),
                error_summary=sanitize_error_summary(item.get("error_summary")),
                stdout_preview=sanitize_preview(item.get("stdout_preview"), limit=160),
            )
            for item in (payload.get("test_results") or [])
        )
        return PythonSandboxRunResult(
            status=status,
            test_results=test_results,
            stdout_preview=sanitize_preview(payload.get("stdout_preview"), limit=160),
            stderr_preview=stderr_preview or sanitize_preview(payload.get("stderr_preview"), limit=160),
            error_summary=sanitize_error_summary(payload.get("error_summary")),
            runtime_ms=int(payload.get("runtime_ms") or 0),
            memory_peak_mb=(float(payload["memory_peak_mb"]) if payload.get("memory_peak_mb") is not None else None),
            policy_violation_code=(str(payload.get("policy_violation_code")) if payload.get("policy_violation_code") else None),
            runner_version=self._runner_version,
            sanitized_metadata=dict(payload.get("sanitized_metadata") or {}),
        )

    def _create_workspace(self) -> str:
        return tempfile.mkdtemp(prefix="exam-sys-python-sandbox-")

    def _cleanup_workspace(self, workspace: str) -> bool:
        try:
            shutil.rmtree(workspace, ignore_errors=False)
            return True
        except FileNotFoundError:
            return True
        except Exception:
            return False

    def _result(
        self,
        *,
        status: str,
        runtime_ms: float,
        error_summary: str | None,
        stdout_preview: str | None = None,
        stderr_preview: str | None = None,
        policy_violation_code: str | None = None,
        sanitized_metadata: dict[str, Any] | None = None,
    ) -> PythonSandboxRunResult:
        return PythonSandboxRunResult(
            status=str(status),
            test_results=tuple(),
            stdout_preview=sanitize_preview(stdout_preview, limit=160),
            stderr_preview=sanitize_preview(stderr_preview, limit=160),
            error_summary=sanitize_error_summary(error_summary),
            runtime_ms=int((perf_counter() - runtime_ms) * 1000),
            memory_peak_mb=None,
            policy_violation_code=policy_violation_code,
            runner_version=self._runner_version,
            sanitized_metadata=dict(sanitized_metadata or {}),
        )