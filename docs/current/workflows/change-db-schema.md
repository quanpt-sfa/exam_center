---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# Change DB Schema

Purpose:

- Change the staged PostgreSQL schema or migration set.

Read-first files:

- `AGENTS.md`
- `database/AGENTS.md`
- `database/README.md`

Search-before-read rule:

- Start from PostgreSQL domain.
- Search migration, table, and function names first.
- Open only the target migration or script and the nearest smoke test after search.

Forbidden default context:

- `reports/**`
- `reports/copy-provenance.json`

Validation:

- Run non-destructive database checker or nearest smoke validation only.

Escalate to audit/readiness mode when:

- Repo-root assumptions appear in scripts.
- The change would require destructive DB scripts or a real database migration run.
