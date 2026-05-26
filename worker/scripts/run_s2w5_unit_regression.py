#!/usr/bin/env python3
"""Run the S2W-5 unit and static regression pack."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]


TEST_GROUPS: list[tuple[str, list[str]]] = [
    (
        "S2W-5.3 capture claim and DSN boundaries",
        [
            "apps/worker/tests/test_capture_job_claim_unit.py",
            "apps/worker/tests/test_capture_dsn_guard_unit.py",
            "apps/worker/tests/test_capture_adapter_boundary_unit.py",
        ],
    ),
    (
        "S2W-5.5 capture worker",
        [
            "apps/worker/tests/test_capture_worker_unit.py",
        ],
    ),
    (
        "S2W-5.6 capture-aware materialization and guards",
        [
            "apps/worker/tests/test_grading_worker_capture_materialization_unit.py",
            "apps/worker/tests/test_capture_route_static_guards.py",
            "apps/worker/tests/test_grading_worker_no_mutable_answer_source_guard.py",
        ],
    ),
]


def _run_group(name: str, tests: list[str]) -> int:
    print(f"\n[GROUP] {name}")
    cmd = [sys.executable, "-m", "pytest", "-q", *tests]
    print("[CMD]", " ".join(cmd))
    completed = subprocess.run(cmd, cwd=REPO_ROOT)
    return int(completed.returncode)


def _run_s2w4_unit_regression() -> int:
    cmd = [sys.executable, "apps/worker/scripts/run_s2w4_unit_regression.py"]
    print("\n[GROUP] S2W-4 unit regression guardrail")
    print("[CMD]", " ".join(cmd))
    completed = subprocess.run(cmd, cwd=REPO_ROOT)
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run S2W-5 unit/static regression pack")
    parser.add_argument(
        "--group",
        action="append",
        default=[],
        help="Optional group name filter (can be passed multiple times)",
    )
    parser.add_argument(
        "--skip-s2w4-unit-regression",
        action="store_true",
        help="Skip the S2W-4 unit regression guardrail",
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

    print("S2W-5 unit/static regression pack")
    print(f"Repo root: {REPO_ROOT}")

    for name, tests in selected_groups:
        rc = _run_group(name, tests)
        if rc != 0:
            print(f"\n[FAIL] Group failed: {name}")
            return rc

    if not args.skip_s2w4_unit_regression:
        rc = _run_s2w4_unit_regression()
        if rc != 0:
            print("\n[FAIL] S2W-4 unit regression guardrail failed.")
            return rc

    print("\n[OK] S2W-5 unit/static regression pack passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
