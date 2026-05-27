# QUICK_EDIT

Purpose:

- Make one small change with minimal context in the standalone runtime.

Do not open by default:

- `reports/**`
- `reports/copy-provenance.json`
- `reports/readiness-audit.md`
- `reports/migration-closure-report.md`
- `docs/archive`
- `docs/evidence`

Required read order:

1. `manifest.yaml`
2. `AGENTS.md`
3. `<domain>/AGENTS.md`
4. `<domain>/README.md`
5. target source file
6. nearest test file

Search-first rule:

- Identify the domain first.
- Search symbol, path, or test name before opening unknown files.
- Open only the target file and nearest test after search narrows scope.

Boundary rule:

- Stay inside the standalone active roots unless the user explicitly asks for historical or archived material.
