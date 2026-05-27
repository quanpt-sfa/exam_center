"""Pytest bootstrapping for standalone worker tests."""

from __future__ import annotations

from pathlib import Path
import sys


TESTS_ROOT = Path(__file__).resolve().parent
WORKER_ROOT = TESTS_ROOT.parent
PROJECT_ROOT = WORKER_ROOT.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"

if not (PROJECT_ROOT / "manifest.yaml").exists():
    raise RuntimeError(f"Standalone project root not found from worker tests: {PROJECT_ROOT}")

for root in (BACKEND_ROOT, WORKER_ROOT):
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
