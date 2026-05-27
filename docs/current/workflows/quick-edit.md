---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# Quick Edit

Purpose:

- Make a small change inside the standalone runtime without opening audit-heavy context.

Read-first files:

- `AGENTS.md`
- `<domain>/AGENTS.md`
- `<domain>/README.md`

Search-before-read rule:

- Identify domain first.
- Search symbol/path before opening source files.
- Read domain context before opening broader code.
- Edit the target file and run the nearest test only after search.

Forbidden default context:

- `reports/`
- `reports/copy-provenance.json`
- `reports/readiness-audit.md`
- `reports/migration-closure-report.md`

Validation:

- Run the smallest relevant domain test or checker only.

Escalate to audit/readiness mode when:

- The target file is unknown after search.
- The change depends on provenance, readiness, or cross-domain routing review.
- The user explicitly asks for historical or archived source material instead of the standalone runtime.
