---
status: active
owner: docs
source_of_truth: true
token_budget: low
---

# Change Worker Job

Purpose:

- Change a staged worker job, queue flow, or config path.

Read-first files:

- `AGENTS.md`
- `worker/AGENTS.md`
- `worker/README.md`

Search-before-read rule:

- Start from worker domain.
- Search job, queue, and config names first.
- Read the worker contract only if behavior changes.

Forbidden default context:

- `reports/**`
- `reports/copy-provenance.json`

Validation:

- Run the nearest worker test or config-check only.

Escalate to audit/readiness mode when:

- Database or script assumptions appear.
- The change would require copying or pulling dependencies from outside `worker/**`.
