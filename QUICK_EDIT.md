# QUICK_EDIT

Purpose:

- Edit, add, or delete one function with minimal context.

Do not open by default:

- `reports/**`
- `reports/copy-provenance.json`
- `reports/readiness-audit.md`
- `reports/migration-closure-report.md`
- `docs/archive`
- `docs/evidence`

Required read order:

1. `AGENTS.md`
2. `manifest.yaml`
3. `<domain>/AGENTS.md`
4. `<domain>/README.md`
5. target source file
6. nearest test file

Search-first rule:

- Identify domain first.
- Use search or grep before opening unknown source files.
- Open the target source file and nearest test only after search.

Boundary rule:

- Stay inside `apps-next` unless the user explicitly asks to edit original source roots.
