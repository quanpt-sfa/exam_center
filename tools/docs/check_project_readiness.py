from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "manifest.yaml"
QUICK_EDIT = REPO_ROOT / "QUICK_EDIT.md"
REQUIRED = (
    REPO_ROOT / "AGENTS.md",
    MANIFEST,
    QUICK_EDIT,
    REPO_ROOT / "docs/00-start-here/manifest.yaml",
    REPO_ROOT / "docs/00-start-here/routing.md",
    REPO_ROOT / "backend/AGENTS.md",
    REPO_ROOT / "backend/README.md",
    REPO_ROOT / "frontend/AGENTS.md",
    REPO_ROOT / "frontend/README.md",
    REPO_ROOT / "worker/AGENTS.md",
    REPO_ROOT / "worker/README.md",
    REPO_ROOT / "database/AGENTS.md",
    REPO_ROOT / "database/README.md",
    REPO_ROOT / "contracts/AGENTS.md",
    REPO_ROOT / "contracts/README.md",
    REPO_ROOT / "reports/readiness-dashboard.md",
)
PROHIBITIONS = (
    "reports/**",
    "copy-provenance.json",
    "readiness-audit.md",
    "migration-closure-report.md",
    "docs/archive",
    "docs/evidence",
)
MANIFEST_AVOID = (
    "reports/**",
    "reports/copy-provenance.json",
    "reports/readiness-audit.md",
    "reports/migration-closure-report.md",
    "docs/archive/**",
    "docs/evidence/**",
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_tasks(path: Path) -> dict[str, dict[str, list[str]]]:
    tasks: dict[str, dict[str, list[str]]] = {}
    current_task = None
    current_section = None
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            current_task = stripped[:-1]
            tasks.setdefault(current_task, {})
            current_section = None
            continue
        if current_task is None:
            continue
        if line.startswith("    ") and not line.startswith("      ") and stripped.endswith(":"):
            current_section = stripped[:-1]
            tasks[current_task].setdefault(current_section, [])
            continue
        if current_section and line.startswith("      - "):
            tasks[current_task].setdefault(current_section, []).append(stripped[2:].strip())
    return tasks


def main() -> int:
    violations: list[str] = []
    for path in REQUIRED:
        if not path.exists():
            violations.append(f"missing required file: {path.relative_to(REPO_ROOT).as_posix()}")
    if QUICK_EDIT.exists():
        content = read_text(QUICK_EDIT)
        for item in PROHIBITIONS:
            if item not in content:
                violations.append(f"QUICK_EDIT.md missing prohibition: {item}")
    if MANIFEST.exists():
        tasks = parse_tasks(MANIFEST)
        quick_edit = tasks.get("quick_edit", {})
        avoid_by_default = set(quick_edit.get("avoid_by_default", []))
        for item in MANIFEST_AVOID:
            if item not in avoid_by_default:
                violations.append(f"manifest quick_edit missing avoid_by_default: {item}")
    frontend_package = REPO_ROOT / "frontend/package.json"
    if not frontend_package.exists():
        violations.append("frontend/package.json missing")
    else:
        payload = json.loads(read_text(frontend_package))
        scripts = payload.get("scripts", {})
        if not isinstance(scripts, dict) or not scripts:
            violations.append("frontend/package.json has no scripts")
    for path in (
        REPO_ROOT / "backend/requirements.txt",
        REPO_ROOT / "backend/requirements-dev.txt",
        REPO_ROOT / "worker/requirements.txt",
        REPO_ROOT / "worker/requirements-dev.txt",
        REPO_ROOT / "backend/app/main.py",
        REPO_ROOT / "worker/worker_runtime/cli.py",
    ):
        if not path.exists():
            violations.append(f"missing runtime readiness file: {path.relative_to(REPO_ROOT).as_posix()}")
    if violations:
        print("check_project_readiness FAILED")
        for item in violations:
            print(f"- {item}")
        return 1
    print("check_project_readiness PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
