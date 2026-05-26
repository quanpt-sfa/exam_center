"""Pytest bootstrapping for greenfield API tests."""

from __future__ import annotations

from pathlib import Path
import sys


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

# Resolve naming collision with a root-level app module.
existing = sys.modules.get("app")
if existing is not None and not hasattr(existing, "__path__"):
    del sys.modules["app"]
