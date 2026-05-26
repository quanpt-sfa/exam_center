"""Static invariants for grading worker runtime safety boundaries."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _runtime_dir() -> Path:
    return _repo_root() / "apps" / "worker" / "worker_runtime" / "grading"


def _build_forbidden_mutable_source_token() -> str:
    return "submission." + "answer_" + "state"


def _build_actual_result_table_token() -> str:
    return "grading." + "actual_" + "result"


def _build_expected_actual_comparison_table_token() -> str:
    return "grading." + "expected_" + "actual_" + "comparison"


def _build_allowed_question_score_table_token() -> str:
    return "grading." + "question_" + "score"


def _build_allowed_submission_score_table_token() -> str:
    return "grading." + "submission_" + "score"


def _build_forbidden_manual_review_queue_insert_token() -> str:
    return "INSERT INTO " + "grading." + "manual_" + "review_" + "queue"


def _build_forbidden_score_adjustment_insert_token() -> str:
    return "INSERT INTO " + "grading." + "score_" + "adjustment"


def _build_allowed_terminal_event_tokens() -> list[str]:
    return [
        "JOB_" + "STARTED",
        "RUN_" + "STARTED",
        "TASK_" + "QUEUED",
        "TASK_" + "STARTED",
        "TASK_" + "COMPLETED",
        "TASK_" + "FAILED",
        "COMPARISON_" + "COMPLETED",
        "SCORE_" + "CREATED",
        "RUN_" + "COMPLETED",
        "RUN_" + "FAILED",
        "JOB_" + "COMPLETED",
        "JOB_" + "FAILED",
    ]


def _build_forbidden_capture_path_tokens() -> list[str]:
    return [
        "worker_runtime." + "capture_" + "worker",
        "capture_" + "to_" + "grading",
        "capture-to-" + "grading",
    ]


def _build_executor_dsn_token() -> str:
    return "TEXTBOX_SQL_" + "EXECUTOR_DSN"


def _build_forbidden_executor_fallback_tokens() -> list[str]:
    return [
        "os.getenv(\"" + _build_executor_dsn_token() + "\",",
        "os.getenv('" + _build_executor_dsn_token() + "',",
        "os.getenv(\"" + _build_executor_dsn_token() + "\") or os.getenv(\"POSTGRES_",
        "os.getenv(\"" + _build_executor_dsn_token() + "\") or os.getenv('POSTGRES_",
        "os.getenv('" + _build_executor_dsn_token() + "') or os.getenv(\"POSTGRES_",
        "os.getenv('" + _build_executor_dsn_token() + "') or os.getenv('POSTGRES_",
    ]


def test_grading_runtime_does_not_reference_mutable_answer_source() -> None:
    repo_root = _repo_root()
    runtime_dir = _runtime_dir()
    forbidden = _build_forbidden_mutable_source_token()

    files = sorted(runtime_dir.rglob("*.py"))
    assert files, "Expected grading runtime scaffold files to exist"

    offenders: list[str] = []
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        if forbidden in content:
            offenders.append(str(file_path.relative_to(repo_root)).replace("\\", "/"))

    assert not offenders, f"Forbidden mutable answer source token found in: {offenders}"


def test_materialization_repository_sql_strings_use_immutable_sources_only() -> None:
    runtime_dir = _runtime_dir()
    repository_path = runtime_dir / "sealed_task_materialization_repository.py"
    assert repository_path.exists(), "Expected sealed task materialization repository to exist"

    content = repository_path.read_text(encoding="utf-8")

    immutable_tables = [
        "submission.sealed_answer",
        "delivery.generated_exam_question",
        "assessment.question_grading_profile",
        "delivery.generated_expected_answer",
    ]
    for table_name in immutable_tables:
        assert table_name in content, f"Expected immutable source table reference missing: {table_name}"

    forbidden = _build_forbidden_mutable_source_token()
    assert forbidden not in content, "Materialization repository must not reference mutable answer source"


def test_grading_runtime_may_reference_question_score_table() -> None:
    runtime_dir = _runtime_dir()
    repository_path = runtime_dir / "textbox_sql_question_score_repository.py"
    assert repository_path.exists(), "Expected textbox_sql_question_score_repository.py to exist"

    content = repository_path.read_text(encoding="utf-8")
    allowed_table = _build_allowed_question_score_table_token()
    assert allowed_table in content, "Expected S2W-4.6 runtime to reference grading.question_score"


def test_grading_runtime_may_reference_submission_score_table() -> None:
    runtime_dir = _runtime_dir()
    repository_path = runtime_dir / "textbox_sql_submission_score_repository.py"
    assert repository_path.exists(), "Expected textbox_sql_submission_score_repository.py to exist"

    content = repository_path.read_text(encoding="utf-8")
    allowed_table = _build_allowed_submission_score_table_token()
    assert allowed_table in content, "Expected S2W-4.6 runtime to reference grading.submission_score"


def test_s2w46_runtime_may_reference_actual_result_table() -> None:
    runtime_dir = _runtime_dir()
    repository_path = runtime_dir / "textbox_sql_actual_result_repository.py"
    assert repository_path.exists(), "Expected textbox_sql_actual_result_repository.py to exist"

    content = repository_path.read_text(encoding="utf-8")
    allowed_table = _build_actual_result_table_token()
    assert allowed_table in content, "Expected S2W-4.6 runtime to reference grading.actual_result"


def test_s2w46_runtime_may_reference_expected_actual_comparison_table() -> None:
    runtime_dir = _runtime_dir()
    repository_path = runtime_dir / "textbox_sql_comparison_repository.py"
    assert repository_path.exists(), "Expected textbox_sql_comparison_repository.py to exist"

    content = repository_path.read_text(encoding="utf-8")
    allowed_table = _build_expected_actual_comparison_table_token()
    assert allowed_table in content, "Expected S2W-4.6 runtime to reference grading.expected_actual_comparison"


def test_grading_runtime_may_emit_final_s2w4_lifecycle_events() -> None:
    runtime_dir = _runtime_dir()

    event_sources: dict[str, tuple[str, ...]] = {
        "grading_job_runtime_repository.py": ("JOB_STARTED", "RUN_STARTED"),
        "sealed_task_materialization_repository.py": ("TASK_QUEUED",),
        "textbox_sql_actual_result_repository.py": ("TASK_STARTED", "TASK_COMPLETED", "TASK_FAILED"),
        "textbox_sql_comparison_repository.py": ("COMPARISON_COMPLETED",),
        "textbox_sql_question_score_repository.py": ("SCORE_CREATED",),
        "textbox_sql_submission_score_repository.py": (
            "RUN_COMPLETED",
            "RUN_FAILED",
            "JOB_COMPLETED",
            "JOB_FAILED",
        ),
    }

    seen_tokens: set[str] = set()
    for filename, expected_tokens in event_sources.items():
        path = runtime_dir / filename
        assert path.exists(), f"Expected runtime event source file to exist: {filename}"

        content = path.read_text(encoding="utf-8")
        for token in expected_tokens:
            assert token in content, f"Expected runtime event token '{token}' in {filename}"
            seen_tokens.add(token)

    assert seen_tokens == set(_build_allowed_terminal_event_tokens())


def test_grading_runtime_may_emit_score_created_event() -> None:
    runtime_dir = _runtime_dir()
    repository_path = runtime_dir / "textbox_sql_question_score_repository.py"
    assert repository_path.exists(), "Expected textbox_sql_question_score_repository.py to exist"

    content = repository_path.read_text(encoding="utf-8")
    assert "SCORE_" + "CREATED" in content, "Expected S2W-4.5 runtime to emit SCORE_CREATED"


def test_grading_runtime_does_not_insert_manual_review_queue_or_score_adjustment() -> None:
    repo_root = _repo_root()
    runtime_dir = _runtime_dir()

    forbidden_insert_tokens = [
        _build_forbidden_manual_review_queue_insert_token(),
        _build_forbidden_score_adjustment_insert_token(),
    ]

    files = sorted(runtime_dir.rglob("*.py"))
    assert files, "Expected grading runtime scaffold files to exist"

    offenders: list[str] = []
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        if any(token in content for token in forbidden_insert_tokens):
            offenders.append(str(file_path.relative_to(repo_root)).replace("\\", "/"))

    assert not offenders, (
        "Out-of-scope manual review/adjustment insert paths found in runtime source: "
        f"{offenders}"
    )


def test_grading_runtime_does_not_reference_capture_worker_paths() -> None:
    repo_root = _repo_root()
    runtime_dir = _runtime_dir()
    forbidden_capture_tokens = _build_forbidden_capture_path_tokens()

    files = sorted(runtime_dir.rglob("*.py"))
    assert files, "Expected grading runtime scaffold files to exist"

    offenders: list[str] = []
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        if any(token in content for token in forbidden_capture_tokens):
            offenders.append(str(file_path.relative_to(repo_root)).replace("\\", "/"))

    assert not offenders, (
        "Out-of-scope capture worker implementation path references found in runtime source: "
        f"{offenders}"
    )


def test_executor_dsn_must_not_fallback_to_application_persistence_dsn() -> None:
    repo_root = _repo_root()
    runtime_dir = _runtime_dir()
    forbidden_patterns = _build_forbidden_executor_fallback_tokens()

    files = sorted(runtime_dir.rglob("*.py"))
    assert files, "Expected grading runtime scaffold files to exist"

    offenders: list[str] = []
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        if any(pattern in content for pattern in forbidden_patterns):
            offenders.append(str(file_path.relative_to(repo_root)).replace("\\", "/"))

    assert not offenders, (
        "Forbidden executor DSN fallback pattern found in runtime source: "
        f"{offenders}"
    )


def test_required_phase_services_have_no_implicit_production_noop_defaults() -> None:
    runtime_dir = _runtime_dir()
    worker_path = runtime_dir / "grading_worker.py"
    assert worker_path.exists(), "Expected grading_worker.py to exist"

    content = worker_path.read_text(encoding="utf-8")
    forbidden_defaults = [
        "task_materialization_service or _TestOnlyNoopTaskMaterializationService(",
        "actual_result_service or _TestOnlyNoopActualResultService(",
        "comparison_service or _TestOnlyNoopComparisonService(",
        "question_score_service or _TestOnlyNoopQuestionScoreService(",
        "submission_score_service or _TestOnlyNoopSubmissionScoreService(",
    ]

    assert "allow_test_scaffold_services" in content, (
        "Expected explicit allow_test_scaffold_services gate for test-only no-op scaffolds"
    )
    assert all(token not in content for token in forbidden_defaults), (
        "Production constructor must not implicitly instantiate test-only no-op services"
    )


def test_cli_must_not_enable_test_scaffold_mode_for_production_worker() -> None:
    repo_root = _repo_root()
    cli_path = repo_root / "apps" / "worker" / "worker_runtime" / "cli.py"
    assert cli_path.exists(), "Expected worker_runtime/cli.py to exist"

    content = cli_path.read_text(encoding="utf-8")
    assert "allow_test_scaffold_services=False" in content, (
        "CLI production wiring must explicitly keep allow_test_scaffold_services disabled"
    )
    assert "allow_test_scaffold_services=True" not in content, (
        "CLI must never enable test scaffold mode"
    )


def test_cli_must_validate_executor_dsn_isolation_before_worker_start() -> None:
    repo_root = _repo_root()
    cli_path = repo_root / "apps" / "worker" / "worker_runtime" / "cli.py"
    assert cli_path.exists(), "Expected worker_runtime/cli.py to exist"

    content = cli_path.read_text(encoding="utf-8")
    assert "validate_textbox_sql_executor_dsn(" in content, (
        "CLI must validate TEXTBOX_SQL executor DSN isolation before worker startup"
    )
    assert "build_app_db_dsn_from_env(" in content, (
        "CLI must build app persistence DSN for equivalence guard checks"
    )
    assert "ALLOW_TEXTBOX_SQL_APP_DB_DSN_FOR_TESTS" in content, (
        "CLI must gate app DB DSN override behind explicit test-only env"
    )


def test_cli_must_fail_fast_for_unsafe_executor_dsn_without_explicit_test_override() -> None:
    repo_root = _repo_root()
    cli_path = repo_root / "apps" / "worker" / "worker_runtime" / "cli.py"
    assert cli_path.exists(), "Expected worker_runtime/cli.py to exist"

    content = cli_path.read_text(encoding="utf-8")
    assert "allow_app_db_for_tests=_allow_textbox_sql_app_db_dsn_for_tests()" in content, (
        "CLI must pass explicit test-only override gate into DSN validation"
    )
    assert "if not bool(dsn_validation.get(\"is_valid\"))" in content, (
        "CLI must fail fast on unsafe executor/app DSN equivalence"
    )
    assert "return 1" in content, "CLI must terminate with non-zero exit on unsafe DSN"
    assert "PYTEST_CURRENT_TEST" in content, (
        "CLI test override gate must require test context via PYTEST_CURRENT_TEST"
    )
    assert "EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION" in content, (
        "CLI test override gate must require integration context when enabled"
    )


def test_direct_textbox_sql_executor_must_exclude_capture_required_tasks() -> None:
    runtime_dir = _runtime_dir()
    repository_path = runtime_dir / "textbox_sql_actual_result_repository.py"
    assert repository_path.exists(), "Expected textbox_sql_actual_result_repository.py to exist"

    content = repository_path.read_text(encoding="utf-8")

    assert "qgt.input_source = 'SEALED_TEXT_ANSWER'" in content, (
        "Direct TEXTBOX_SQL executor must only claim SEALED_TEXT_ANSWER tasks"
    )
    assert "qgt.requires_capture = false" in content, (
        "Direct TEXTBOX_SQL executor must not claim capture-required tasks"
    )
