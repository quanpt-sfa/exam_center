---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# Token Budget

Purpose:

- Keep editing context narrow and predictable.

When to read:

- Before opening more than the first small set of docs.

When not to read:

- Do not treat this as a substitute for code or tests.

Token budgets:

- Quick edit: `5k-12k`
- One-domain add function: `10k-20k`
- Small backend+frontend feature: `20k-40k`
- Audit/readiness: may be higher, but only for audit tasks

Forbidden default context:

- `reports/**`
- `reports/copy-provenance.json`
- `reports/readiness-audit.md`
- `reports/migration-closure-report.md`

Search-before-read rule:

- Identify the domain first.
- Search symbol names, file paths, or route names before opening heavy files.
- Summarize what you found before expanding context.

Next files to inspect:

- `manifest.yaml`
- `routing.md`
