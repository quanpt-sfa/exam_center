"""Standalone-safe worker test paths."""

from __future__ import annotations

from pathlib import Path


TESTS_ROOT = Path(__file__).resolve().parent
WORKER_ROOT = TESTS_ROOT.parent
PROJECT_ROOT = WORKER_ROOT.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
WORKER_RUNTIME_ROOT = WORKER_ROOT / "worker_runtime"
CAPTURE_RUNTIME_ROOT = WORKER_RUNTIME_ROOT / "capture"
GRADING_RUNTIME_ROOT = WORKER_RUNTIME_ROOT / "grading"

if not (PROJECT_ROOT / "manifest.yaml").exists():
    raise RuntimeError(f"Standalone project root not found: {PROJECT_ROOT}")

for required in (WORKER_ROOT, BACKEND_ROOT, WORKER_RUNTIME_ROOT):
    if not required.exists():
        raise RuntimeError(f"Required standalone path missing: {required}")
