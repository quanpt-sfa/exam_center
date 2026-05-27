"""Pytest bootstrapping for greenfield API tests."""

from __future__ import annotations

import os
from pathlib import Path
import sys


API_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = API_ROOT.parent
CONTRACTS_ROOT = PROJECT_ROOT / "contracts"
CONTRACTS_API_ROOT = CONTRACTS_ROOT / "api"
CONTRACTS_DEPLOYMENT_ROOT = CONTRACTS_ROOT / "deployment"
DATABASE_POSTGRES_ROOT = PROJECT_ROOT / "database" / "postgres"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

# Resolve naming collision with a root-level app module.
existing = sys.modules.get("app")
if existing is not None and not hasattr(existing, "__path__"):
    del sys.modules["app"]

os.environ.setdefault("EXAM_CENTER_PROJECT_ROOT", str(PROJECT_ROOT))
