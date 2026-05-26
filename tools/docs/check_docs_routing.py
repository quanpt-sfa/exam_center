from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_MANIFEST = REPO_ROOT / "manifest.yaml"
DOCS_MANIFEST = REPO_ROOT / "docs/00-start-here/manifest.yaml"
ROUTING = REPO_ROOT / "docs/00-start-here/routing.md"
QUICK_EDIT_WORKFLOW = REPO_ROOT / "docs/current/workflows/quick-edit.md"
ACTIVE_DOCS = (
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "QUICK_EDIT.md",
    ROOT_MANIFEST,
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
FORBIDDEN_PATHS = (
    "apps-next/",
    "docs-next/",
    "apps/api/",
    "apps/frontend/",
    "apps/worker/",
    "db/postgres/",
)
FORBIDDEN_REPORTS = (
    "reports/**",
    "reports/copy-provenance.json",
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
    for path in (ROOT_MANIFEST, DOCS_MANIFEST, ROUTING, QUICK_EDIT_WORKFLOW):
        if not path.exists():
            violations.append(f"missing routing file: {path.relative_to(REPO_ROOT).as_posix()}")
    if violations:
        print("check_docs_routing FAILED")
        for item in violations:
            print(f"- {item}")
        return 1
    root_tasks = parse_tasks(ROOT_MANIFEST)
    docs_tasks = parse_tasks(DOCS_MANIFEST)
    for task_name, task in {**root_tasks, **docs_tasks}.items():
        if "read_first" in task and "audit" not in task_name and "readiness" not in task_name and len(task["read_first"]) > 3:
            violations.append(f"{task_name} exceeds read_first budget")
    quick_edit_root = root_tasks.get("quick_edit", {})
    for item in FORBIDDEN_REPORTS:
        if item not in set(quick_edit_root.get("avoid_by_default", [])):
            violations.append(f"root quick_edit missing avoid-by-default: {item}")
    docs_quick_edit = docs_tasks.get("quick_edit", {})
    docs_paths = docs_quick_edit.get("read_first", []) + docs_quick_edit.get("read_if_needed", [])
    for item in FORBIDDEN_REPORTS:
        if item in docs_paths:
            violations.append(f"docs quick_edit routes into forbidden path: {item}")
    files = [ROOT_MANIFEST, DOCS_MANIFEST, ROUTING, QUICK_EDIT_WORKFLOW]
    files.extend(
        path
        for path in (REPO_ROOT / "docs/current/workflows").rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".yaml", ".yml"}
    )
    files.extend(path for path in ACTIVE_DOCS if path.exists())
    seen = set()
    for path in files:
        if path in seen:
            continue
        seen.add(path)
        text = read_text(path)
        for line_no, line in enumerate(text.splitlines(), start=1):
            for family in FORBIDDEN_PATHS:
                if family in line:
                    violations.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{line_no}: forbidden old path {family}")
    if violations:
        print("check_docs_routing FAILED")
        for item in violations:
            print(f"- {item}")
        return 1
    print("check_docs_routing PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
