#!/usr/bin/env python3
"""Run UE2E browser tests for apps/frontend.

This runner expects API and frontend servers to already be running.
It does not auto-start services to avoid mutating existing dev workflows.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


FRONTEND_DIR = Path(__file__).resolve().parents[1]


def _mask(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "<empty>"
    if len(text) <= 4:
        return "<redacted>"
    return f"{text[:2]}***{text[-2:]}"


def _sanitized_snapshot() -> dict[str, str]:
    return {
        "FRONTEND_BASE_URL": str(os.getenv("FRONTEND_BASE_URL", "http://127.0.0.1:5173")).strip(),
        "API_BASE_URL": str(os.getenv("API_BASE_URL", "http://127.0.0.1:8000")).strip(),
        "UE2E_RUN_INTEGRATION": str(os.getenv("UE2E_RUN_INTEGRATION", "0")).strip(),
        "UE2E_AUTH_MODE": str(os.getenv("UE2E_AUTH_MODE", "bearer")).strip(),
        "UE2E_STUDENT_A_LOGIN": _mask(str(os.getenv("UE2E_STUDENT_A_LOGIN", ""))),
        "UE2E_STUDENT_B_LOGIN": _mask(str(os.getenv("UE2E_STUDENT_B_LOGIN", ""))),
    }


def _run(command: list[str]) -> int:
    print("[CMD]", " ".join(command))
    completed = subprocess.run(command, cwd=FRONTEND_DIR, check=False)
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run UE2E Playwright scenarios")
    parser.add_argument(
        "--with-unit-tests",
        action="store_true",
        help="Run npm test before npm run e2e",
    )
    args = parser.parse_args()

    print("UE2E runner (apps/frontend)")
    print(f"[INFO] Frontend directory: {FRONTEND_DIR}")
    print("[INFO] Sanitized environment snapshot:")
    for key, value in _sanitized_snapshot().items():
        print(f"- {key}={value}")

    print("[INFO] This runner expects API and frontend dev servers to already be running.")

    if args.with_unit_tests:
        rc = _run(["npm", "test"])
        if rc != 0:
            print("[FAIL] npm test failed")
            return rc

    rc = _run(["npm", "run", "e2e"])
    if rc != 0:
        print("[FAIL] npm run e2e failed")
        return rc

    print("[OK] UE2E run completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
