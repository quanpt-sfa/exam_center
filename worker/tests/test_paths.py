"""Standalone-safe worker test paths."""

from __future__ import annotations

from pathlib import Path


TESTS_ROOT = Path(__file__).resolve().parent
_current = TESTS_ROOT
PROJECT_ROOT: Path | None = None

while True:
    candidate = _current
    if (
        (candidate / "manifest.yaml").exists()
        and (candidate / "backend").is_dir()
        and (candidate / "worker").is_dir()
        and (candidate / "database").is_dir()
    ):
        PROJECT_ROOT = candidate
        break
    if candidate.parent == candidate:
        break
    _current = candidate.parent

if PROJECT_ROOT is None:
    raise RuntimeError(f"Standalone project root not found from worker tests: {TESTS_ROOT}")

WORKER_ROOT = PROJECT_ROOT / "worker"
BACKEND_ROOT = PROJECT_ROOT / "backend"
DATABASE_POSTGRES_ROOT = PROJECT_ROOT / "database" / "postgres"
WORKER_RUNTIME_ROOT = WORKER_ROOT / "worker_runtime"
CAPTURE_RUNTIME_ROOT = WORKER_RUNTIME_ROOT / "capture"
GRADING_RUNTIME_ROOT = WORKER_RUNTIME_ROOT / "grading"

for required in (WORKER_ROOT, BACKEND_ROOT, DATABASE_POSTGRES_ROOT, WORKER_RUNTIME_ROOT):
    if not required.exists():
        raise RuntimeError(f"Required standalone path missing: {required}")
