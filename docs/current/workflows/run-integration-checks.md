---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# Run Integration Checks

Purpose:

- Run non-destructive staged validation without switching into full readiness audit by default.

Read-first files:

- `AGENTS.md`
- `manifest.yaml`
- `reports/migration-closure-report.md`

Search-before-read rule:

- Identify the staged domain or checker first.
- Search command names and nearest validation entrypoints before opening broader docs.
- Open only the target checker or nearest test command after search.

Forbidden default context:

- full provenance review unless the task is explicitly audit/readiness

Validation:

- `python tools/docs/check_project_readiness.py`
- `python tools/docs/check_legacy_boundaries.py`
- `python tools/docs/check_docs_routing.py`
- `python tools/docs/check_docs_next_routing.py`

Escalate to audit/readiness mode when:

- Quick validation passes but staging-readiness questions remain.
- A checker failure points to cross-domain status, provenance, or report consistency work.
- A real database migration or destructive command would be required.
