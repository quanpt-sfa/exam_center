---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# Standalone Runtime Consolidation Notes

## 1. Objective

Create a staged, agent-friendly the standalone tree workspace that contains only current-project runtime and contract material. The workspace is for cleanup, validation, and future migration rehearsal only; it is not canonical until a later approval explicitly promotes it.

## 2. Non-goals

- Do not copy code in this planning phase.
- Do not modify runtime code.
- Do not delete, move, or rewrite existing source paths.
- Do not preserve a parallel runtime.
- Do not make the standalone tree the default build, test, deployment, or documentation target.
- Do not include historical files outside the current documentation system.

## 3. Source paths allowed for copying

Allowed current source paths:

- `backend/**`
- `frontend/**`
- `worker/**`
- `database/postgres/**`
- `contracts/api/**`
- `contracts/deployment/**`
- `contracts/worker/**`
- `docs/00-start-here/**`
- `docs/current/**`
- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- `.claude/rules/**`
- `.gemini/settings.json`
- `tools/docs/check_current_docs_only.py`
- `tests/test_current_docs_only.py`

Optional support files may be copied only when needed to run validation from the staged workspace:

- package manager manifests for `frontend/**`
- Python dependency manifests for `backend/**` and `worker/**`
- database script support files under `database/postgres/**`

## 4. Paths excluded from copying

Exclude all paths outside the allowed source list. Historical files outside the current documentation system remain in place in the original repository and are not copied into the standalone tree.

Also exclude generated artifacts, local secrets, local environment files, caches, build output, logs, screenshots, database dumps, token dumps, and dependency directories.

## 5. Proposed the standalone tree directory tree

```text
exam_center/
  backend/
  frontend/
  worker/
  database/
    postgres/
  contracts/
    api/
    deployment/
    worker/
  docs/
  tools/
```

Directory intent:

- `backend/`: FastAPI backend runtime.
- `frontend/`: staged React/Vite frontend copy from `frontend/**`.
- `worker/`: staged worker runtime copy from `worker/**`.
- `database/postgres/`: staged PostgreSQL runtime copy from `database/postgres/**`.
- `contracts/api/`: staged API contract docs from `contracts/api/**`.
- `contracts/deployment/`: staged deployment and runtime contract docs from `contracts/deployment/**`.
- `contracts/worker/`: worker docs from `contracts/worker/**`.
- `docs/`: current routing and workflow docs.
- `tools/docs/`: documentation checkers.

## 6. Copy phases

1. Inventory and allowlist phase: generate a dry-run file list from allowed source paths only, then review it before any copy.
2. Skeleton phase: create empty the standalone tree directories and a staging README that says the workspace is not canonical.
3. Runtime copy phase: copy `backend/**`, `frontend/**`, `worker/**`, and `database/postgres/**` without rewriting imports or commands.
4. Contract copy phase: copy `contracts/api/**`, `contracts/deployment/**`, and `contracts/worker/**` into `contracts/`.
5. Current docs copy phase: copy `docs/00-start-here/**` and `docs/current/**` into `docs/`.
6. Tooling copy phase: copy the current-docs checker and docs-specific test into the staged tooling area.
7. Verification phase: run staging checkers and compare staged file inventory against the allowlist.
8. Review phase: document differences, blockers, and any required follow-up before considering promotion.

## 7. Validation and checker plan

Minimum validation before any staged workspace is accepted:

- Run `python tools/docs/check_current_docs_only.py` in the original repository.
- Keep a standalone inventory checker that fails if active landing docs point outside the allowed source paths.
- Add a future staged-docs checker that verifies `docs/**` remains current-only.
- Compare the staged file list against the approved dry-run allowlist.
- Run focused runtime validation from the original source paths before treating staged results as meaningful.
- Run staged validation only after import paths, package roots, and script working directories are explicitly reviewed.

Validation must not report staged runtime parity until tests actually run from the standalone tree.

## 8. Risks

- Import paths and working directories may assume the original repository layout.
- Frontend package scripts may assume the original app path.
- Worker CLI paths may need staging-aware command wrappers.
- Database scripts may depend on relative paths from `database/postgres/**`.
- Contract docs may contain repo-relative links that need a link audit after copying.
- Duplicating current docs can create drift unless the standalone tree remains clearly marked as staging.
- Promotion pressure can blur the boundary before staged tests and release gates exist.

## 9. Acceptance criteria

- The the standalone tree plan is current-runtime-only.
- No code is copied during the planning phase.
- No existing runtime code is modified.
- The copy allowlist is explicit and narrow.
- Historical files outside the current documentation system are excluded.
- The proposed tree separates runtime, contracts, docs, tools, and docs tests.
- Copy phases are small enough for reviewable PRs.
- Validation includes current-docs checks, inventory checks, and staged runtime checks before any promotion.
- the standalone tree remains a staging workspace until explicitly approved as canonical.
