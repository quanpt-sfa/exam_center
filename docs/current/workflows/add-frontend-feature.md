---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# Add Frontend Feature

Purpose:

- Add or extend a React/Vite feature in the staged frontend runtime.

Read-first files:

- `AGENTS.md`
- `frontend/AGENTS.md`
- `frontend/README.md`

Search-before-read rule:

- Start from frontend domain.
- Search component, API-client, and test names first.
- Read the API contract only if needed.

Forbidden default context:

- `reports/**`
- `reports/copy-provenance.json`
- excluded non-frontend source roots

Validation:

- Run the nearest frontend test first.

Escalate to audit/readiness mode when:

- The feature depends on staged runtime boundaries or provenance review.
- The change requires editing original source roots instead of `apps-next`.
