# Contracts

Purpose:
- Hold the staged current contract docs under `contracts/**`.

Current staging status:
- API, deployment, and worker contract docs listed in inventory are staged from the approved current documentation roots.

Copied source roots:
- `contracts/api/**`
- `contracts/deployment/**`
- `contracts/worker/**`

Read-first files:
- `contracts/AGENTS.md`
- `contracts/api/submission_processing_status_contract.md`
- `contracts/deployment/deployment_runbook.md`
- `contracts/worker/worker_runtime_dev_runbook.md`

Validation/checker references:
- `python tools/docs/check_project_readiness.py`
- `python tools/docs/check_legacy_boundaries.py`

Known limitation:
- Some copied contract docs still assume repo-root runtime paths that are outside the contract-copy allowlist; those references stay documented in `reports/unresolved-imports.md`.
