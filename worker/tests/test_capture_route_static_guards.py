"""Static invariants for S2W-5 capture route safety boundaries."""

from __future__ import annotations

from pathlib import Path

from test_paths import CAPTURE_RUNTIME_ROOT
from test_paths import PROJECT_ROOT
from test_paths import WORKER_RUNTIME_ROOT


def _repo_root() -> Path:
    return PROJECT_ROOT


def _capture_runtime_dir() -> Path:
    return CAPTURE_RUNTIME_ROOT


def _read_text(path: Path) -> str:
    assert path.exists(), f"Expected file to exist: {path}"
    return path.read_text(encoding="utf-8")


def test_capture_runtime_does_not_reference_mutable_answer_state() -> None:
    repo_root = _repo_root()
    runtime_dir = _capture_runtime_dir()
    forbidden = "submission." + "answer_" + "state"

    files = sorted(runtime_dir.rglob("*.py"))
    assert files, "Expected capture runtime files to exist"

    offenders: list[str] = []
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        if forbidden in content:
            offenders.append(str(file_path.relative_to(repo_root)).replace("\\", "/"))

    assert not offenders, f"Forbidden mutable source token found in capture runtime: {offenders}"


def test_capture_runtime_dsn_guard_is_fail_closed_without_app_db_fallback() -> None:
    dsn_guard_path = _capture_runtime_dir() / "capture_dsn_guard.py"
    content = _read_text(dsn_guard_path)

    assert "source_dsn_missing" in content
    assert "no fallback to application DB DSN is allowed" in content

    forbidden_patterns = [
        "os.getenv(\"STUDENT_CAPTURE_SOURCE_DSN\") or os.getenv(\"POSTGRES_",
        "os.getenv('STUDENT_CAPTURE_SOURCE_DSN') or os.getenv(\"POSTGRES_",
        "os.getenv(\"STUDENT_CAPTURE_SOURCE_DSN\") or build_app_db_dsn_from_env(",
    ]
    assert all(pattern not in content for pattern in forbidden_patterns), (
        "Capture route must not fallback from STUDENT_CAPTURE_SOURCE_DSN to app DB DSN"
    )


def test_capture_source_dsn_equivalent_to_app_db_is_rejected_in_production() -> None:
    dsn_guard_path = _capture_runtime_dir() / "capture_dsn_guard.py"
    content = _read_text(dsn_guard_path)

    assert "if equivalent and not allow_app_db_for_tests:" in content
    assert '"reason_code": "source_dsn_matches_app_db"' in content
    assert "blocked in production" in content


def test_production_cli_does_not_enable_deterministic_test_adapter() -> None:
    cli_path = WORKER_RUNTIME_ROOT / "cli.py"
    content = _read_text(cli_path)

    assert "--use-deterministic-test-adapter" in content
    assert "--allow-app-db-dsn-for-tests" in content
    assert "--use-deterministic-test-adapter requires --allow-app-db-dsn-for-tests in test context" in content
    assert "PYTEST_CURRENT_TEST" in content
    assert "EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION" in content


def test_capture_route_does_not_insert_manual_review_queue() -> None:
    repo_root = _repo_root()
    runtime_dir = _capture_runtime_dir()
    forbidden_insert = "INSERT INTO " + "grading." + "manual_" + "review_" + "queue"

    files = sorted(runtime_dir.rglob("*.py"))
    assert files, "Expected capture runtime files to exist"

    offenders: list[str] = []
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        if forbidden_insert in content:
            offenders.append(str(file_path.relative_to(repo_root)).replace("\\", "/"))

    assert not offenders, f"Out-of-scope manual review insert path found: {offenders}"


def test_capture_route_does_not_insert_score_adjustment() -> None:
    repo_root = _repo_root()
    runtime_dir = _capture_runtime_dir()
    forbidden_insert = "INSERT INTO " + "grading." + "score_" + "adjustment"

    files = sorted(runtime_dir.rglob("*.py"))
    assert files, "Expected capture runtime files to exist"

    offenders: list[str] = []
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        if forbidden_insert in content:
            offenders.append(str(file_path.relative_to(repo_root)).replace("\\", "/"))

    assert not offenders, f"Out-of-scope score adjustment insert path found: {offenders}"
