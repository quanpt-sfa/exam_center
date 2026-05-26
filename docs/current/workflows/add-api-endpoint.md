---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# Add API Endpoint

Purpose:

- Add or extend a backend endpoint in the staged current runtime.

Read-first files:

- `AGENTS.md`
- `backend/AGENTS.md`
- `backend/README.md`

Search-before-read rule:

- Start from backend domain.
- Search route, router, schema, and test names first.
- Read the API contract only if the endpoint changes external behavior.

Forbidden default context:

- `reports/**`
- `reports/copy-provenance.json`

Validation:

- Run the nearest backend test first.

Escalate to audit/readiness mode when:

- The endpoint depends on staged provenance or readiness status.
- The change spans multiple staged domains.
