#!/usr/bin/env python3
"""Run the S2W-4 unit and static regression pack."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]


TEST_GROUPS: list[tuple[str, list[str]]] = [
    (
        "S2W-4.1 and S2W-4.2",
        [
            "apps/worker/tests/test_grading_worker_claim_run_unit.py",
            "apps/worker/tests/test_grading_worker_task_materialization_unit.py",
        ],
    ),
    (
        "S2W-4.3",
        [
            "apps/worker/tests/test_grading_worker_textbox_sql_actual_result_unit.py",
            "apps/worker/tests/test_textbox_sql_actual_result_service_unit.py",
            "apps/worker/tests/test_textbox_sql_executor_unit.py",
            "apps/worker/tests/test_textbox_sql_policy.py",
            "apps/worker/tests/test_textbox_sql_result_normalizer.py",
        ],
    ),
    (
        "S2W-4.4",
        [
            "apps/worker/tests/test_grading_worker_textbox_sql_comparison_unit.py",
            "apps/worker/tests/test_textbox_sql_comparison_service_unit.py",
            "apps/worker/tests/test_textbox_sql_expected_payload_parser.py",
            "apps/worker/tests/test_textbox_sql_result_set_comparator.py",
        ],
    ),
    (
        "S2W-4.5",
        [
            "apps/worker/tests/test_grading_worker_textbox_sql_question_score_unit.py",
            "apps/worker/tests/test_textbox_sql_question_score_policy.py",
            "apps/worker/tests/test_textbox_sql_question_score_service_unit.py",
        ],
    ),
    (
        "S2W-4.6",
        [
            "apps/worker/tests/test_grading_worker_textbox_sql_submission_score_unit.py",
            "apps/worker/tests/test_textbox_sql_submission_score_policy.py",
            "apps/worker/tests/test_textbox_sql_submission_score_service_unit.py",
        ],
    ),
    (
        "S2W-4H hardening and static guards",
        [
            "apps/worker/tests/test_grading_worker_service_wiring_hardening.py",
            "apps/worker/tests/test_grading_worker_claim_resume_unit.py",
            "apps/worker/tests/test_textbox_sql_sandbox_dsn_guard.py",
            "apps/worker/tests/test_grading_worker_no_mutable_answer_source_guard.py",
            "apps/worker/tests/test_grading_worker_cli.py",
        ],
    ),
]


def _run_group(name: str, tests: list[str]) -> int:
    print(f"\n[GROUP] {name}")
    cmd = [sys.executable, "-m", "pytest", "-q", *tests]
    print("[CMD]", " ".join(cmd))
    completed = subprocess.run(cmd, cwd=REPO_ROOT)
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run S2W-4 unit/static regression pack")
    parser.add_argument(
        "--group",
        action="append",
        default=[],
        help="Optional group name filter (can be passed multiple times)",
    )
    args = parser.parse_args()

    selected_groups = TEST_GROUPS
    if args.group:
        wanted = {str(item).strip().lower() for item in args.group if str(item).strip()}
        selected_groups = [
            (name, tests)
            for name, tests in TEST_GROUPS
            if name.strip().lower() in wanted
        ]
        if not selected_groups:
            print("[ERROR] No matching groups were selected.")
            return 2

    print("S2W-4 unit/static regression pack")
    print(f"Repo root: {REPO_ROOT}")

    for name, tests in selected_groups:
        rc = _run_group(name, tests)
        if rc != 0:
            print(f"\n[FAIL] Group failed: {name}")
            return rc

    print("\n[OK] S2W-4 unit/static regression pack passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
