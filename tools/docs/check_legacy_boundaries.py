from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = (
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "QUICK_EDIT.md",
    REPO_ROOT / "manifest.yaml",
    REPO_ROOT / "docs/00-start-here",
    REPO_ROOT / "docs/current/workflows",
    REPO_ROOT / "backend/AGENTS.md",
    REPO_ROOT / "backend/README.md",
    REPO_ROOT / "frontend/AGENTS.md",
    REPO_ROOT / "frontend/README.md",
    REPO_ROOT / "worker/AGENTS.md",
    REPO_ROOT / "worker/README.md",
    REPO_ROOT / "database/AGENTS.md",
    REPO_ROOT / "database/README.md",
    REPO_ROOT / "database/postgres/README.md",
    REPO_ROOT / "contracts/AGENTS.md",
    REPO_ROOT / "contracts/README.md",
)
FORBIDDEN_TERMS = (
    "python app.py",
    "app_factory/",
    "routes/",
    "templates/",
    "static/",
    "database/connection.py",
    "pyodbc",
    "apps-next/",
    "docs-next/",
    "apps/api/",
    "apps/frontend/",
    "apps/worker/",
    "db/postgres/",
)


def iter_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        if root.is_file():
            files.append(root)
        else:
            files.extend(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in {".md", ".yaml", ".yml", ".txt"})
    return files


def main() -> int:
    violations: list[str] = []
    seen = set()
    for path in iter_files():
        if path in seen:
            continue
        seen.add(path)
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for term in FORBIDDEN_TERMS:
                if term in line:
                    violations.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{line_no}: {term}")
    if violations:
        print("check_legacy_boundaries FAILED")
        for item in violations:
            print(f"- {item}")
        return 1
    print("check_legacy_boundaries PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
