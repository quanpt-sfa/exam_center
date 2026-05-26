# Readiness Dashboard

Current status:

- `agent-editing-workspace-candidate`

Living status file:

- This dashboard is the default readiness entry point.
- Detailed planning and audit reports are classified in `reports/documentation-sprawl-index.md`.

Staged domains summary:

- Backend staged from `backend/**`
- Database/PostgreSQL staged from `database/postgres/**`
- Contracts staged from `contracts/api/**`, `contracts/deployment/**`, and `contracts/worker/**`
- Worker staged from `worker/**`
- Frontend staged from `frontend/**`

Blocker count:

- `0`

Current blockers:

- None from the current readiness checker set.

Non-blocking issue count:

- `5`

Current non-blocking issues:

- Several staged domains still assume repo-root execution context.
- Contracts still point at runtime/test paths outside their local staged tree.
- `apps-next` remains a staging workspace and is not ready for cutover.
- Several detailed reports remain available as snapshots but are excluded from quick-edit context.
- Staged capture profile fixtures still contain external database resource labels allowed by targeted readiness checker exceptions.

Checker commands:

- `python tools/docs/check_project_readiness.py`
- `python tools/docs/check_legacy_boundaries.py`
- `python tools/docs/check_docs_routing.py`
- `python tools/docs/check_docs_next_routing.py`

Next recommended action:

- Keep `apps-next` as a staged editing candidate and run targeted integration checks before any cutover planning.

Standalone-normalization dry-run checklist:

- Path rewrites needed: map `backend/**` to `backend/**`, `frontend/**` to `frontend/**`, `worker/**` to `worker/**`, `database/**` to `database/**`, `contracts/**` to `contracts/**`, `docs/**` to `docs/**`, selected checker tools to `tools/docs/**`, and selected staged reports to `reports/**`.
- Manifest rewrite needed: replace active route paths with standalone roots and remove source-root references to `backend/`, `frontend/`, `worker/`, `database/postgres/`, `contracts/api/`, `contracts/deployment/`, and `contracts/worker/`.
- Checker rename needed: keep provenance/readiness checks target-aware, then rename docs checker assumptions to standalone `backend`, `frontend`, `worker`, `database/postgres`, `contracts`, `docs`, and `reports` roots.
- Dependency localization needed: verify package files, env examples, scripts, imports, and commands no longer assume original repository-root layout before extraction.
- Reports to keep as snapshots: migration closure, readiness audit, checker preflight, restructuring plan, and copy inventory/provenance history.
- Reports to exclude from default context: all `reports/**` files except this dashboard when explicitly running readiness work.
- Remaining blockers: none from current checkers; standalone extraction still requires path rewrite, manifest rewrite, checker rewrite, and integration validation.

Future standalone path policy:

- `backend/**` is canonical backend.
- `frontend/**` is canonical frontend.
- `worker/**` is canonical worker.
- `database/postgres/**` is canonical PostgreSQL runtime.
- `contracts/**` is canonical contract reference.
- `docs/**` is routing/reference layer.
- `reports/**` is audit-only.
- Active standalone routing docs must not retain the standalone tree, `docs/`, or original source-root terminology.

Detailed report policy:

- Detailed reports are snapshots only and should not be part of default quick-edit context.
- New detailed audits should become dated snapshots, not new default routing docs.
