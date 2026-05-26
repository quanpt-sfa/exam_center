# LAN-1 Deployment Readiness Plan (LAN-Only)

## 1. Scope and Non-Claims

This plan covers LAN-only deployment readiness for the current repository.

Scope:
- One LAN server hosts PostgreSQL, API, worker runtime, and frontend.
- LAN clients access the system via browser.
- Readiness inventory and runbook planning only.

Non-claims:
- No cloud deployment claim.
- No production deployment claim.
- No hosted/staging DB integration pass claim.

Mode decision:
- Hosted/staging DB integration via `CI_PG_*` is currently not applicable for this LAN-only model and remains pending.

## 2. LAN Topology

Target topology:
- LAN server:
  - PostgreSQL database
  - API backend (FastAPI)
  - Worker orchestration runtime
  - Frontend web app server (Vite dev/preview for current draft)
- LAN clients:
  - Browser only
  - No direct DB access

Logical flow:
1. Client browser -> Frontend (LAN server)
2. Frontend -> API (`/api/v1/...`) on LAN server
3. API/Worker -> PostgreSQL on LAN server

## 3. Server and Client Roles

Server role:
- Runs long-lived backend/frontend processes.
- Holds runtime and maintenance DB credentials in local environment only.
- Executes backup/restore drill and DB smoke operations.

Client role:
- Uses browser to access frontend route(s), including submission result pages.
- Must not receive secret material.

## 4. Required Ports and Network Policy

| Port | Component | Direction | LAN policy |
|---|---|---|---|
| 8000/TCP | API backend | client -> server | allow from LAN clients if frontend calls API directly from browser |
| 5173/TCP | Frontend dev/preview | client -> server | allow from LAN clients for browser access |
| 5432/TCP | PostgreSQL | server-local preferred | block from client network unless explicitly required and approved |

Firewall note:
- Open only minimum required LAN ports.
- Prefer DB access restricted to server host/processes.

## 5. Current Command Inventory (Exact)

LAN-3C recommended script sequence (Windows):
1. `scripts\lan\start_lan_all.bat -ServerLanIp 192.168.1.11 -PsqlPath "<psql-path>"`
2. Launcher behavior:
  - Runs `prepare_lan_runtime.ps1` first.
  - If prepare fails, no service windows are opened.
  - Opens API/worker/frontend in separate visible PowerShell windows so logs remain visible.
  - Optionally opens health-check window.

Manual fallback sequence:
1. `powershell -ExecutionPolicy Bypass -File scripts/lan/start_lan_stack.ps1`
2. Run printed commands in separate terminals for API/worker/frontend/health.

Alternative explicit sequence:
1. `powershell -ExecutionPolicy Bypass -File scripts/lan/prepare_lan_runtime.ps1`
2. `powershell -ExecutionPolicy Bypass -File scripts/lan/start_api_lan.ps1 -SkipPrepare`
3. `powershell -ExecutionPolicy Bypass -File scripts/lan/start_worker_lan.ps1 -SkipPrepare`
4. `powershell -ExecutionPolicy Bypass -File scripts/lan/start_frontend_lan.ps1 -SkipPrepare`
5. `powershell -ExecutionPolicy Bypass -File scripts/lan/check_lan_health.ps1 -SkipPrepare`

Boundary note:
- WRO PostgreSQL integration and S2W-7 E2E PostgreSQL integration are not LAN-3 preflight checks.
- `check_lan_db_baseline.ps1` is the LAN runtime DB safety gate in this phase and is not a migration/reset tool.

PostgreSQL checks:
- Runtime role connectivity:
  - `psql -h $env:POSTGRES_HOST -p $env:POSTGRES_PORT -U $env:POSTGRES_USER -d $env:POSTGRES_DB -v ON_ERROR_STOP=1 -c "SELECT current_user, current_database();"`
- Maintenance role connectivity:
  - `psql -h $env:POSTGRES_MAINTENANCE_HOST -p $env:POSTGRES_MAINTENANCE_PORT -U $env:POSTGRES_MAINTENANCE_USER -d $env:POSTGRES_MAINTENANCE_DB -v ON_ERROR_STOP=1 -c "SELECT current_user, current_database();"`

API backend start:
- `Set-Location backend`
- `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` (current local rehearsal baseline)

Worker runtime/orchestration:
- `python -m worker_runtime.cli config-check --role all`
- `python -m worker_runtime.cli run-dispatcher --worker-id dispatcher-01`
- `python -m worker_runtime.cli run-capture --worker-id capture-01`
- `python -m worker_runtime.cli run-grading --worker-id grading-01`
- `python -m worker_runtime.cli run-all --roles dispatcher,capture,grading`

Frontend:
- `Set-Location frontend`
- `npm install`
- `npm run dev`
- `npm run build`
- `npm run preview`

Health/status checks:
- API health: `curl.exe http://127.0.0.1:8000/api/v1/health`
- API DB health: `curl.exe http://127.0.0.1:8000/api/v1/db-health`
- DB release smokes: `python scripts/run_db_release_smokes.py --psql-path <psql-path>`

Result polling endpoint contract:
- Backend endpoint: `GET /api/v1/submissions/{examSubmissionId}/processing-status`
- Frontend route: `/submissions/:examSubmissionId/result`

## 6. Environment Variable Contract for LAN Mode

Authoritative LAN-3B contract and templates:
- `contracts/deployment/lan_env_config_contract.md`
- `.env.lan.example`

Template and generation intent:
- Operator edits only root `.env.lan`.
- Service files `backend/.env.lan`, `worker/.env.lan`, and `frontend/.env.lan` are generated automatically.
- Service generated files must not be edited manually.
- Real `.env`/`.env.local`/`.env.lan` files remain local-only and must not be committed.
- Do not commit root `.env.lan` or generated service `.env.lan` files.

API required:
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_SSLMODE`
- `EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET`
- `EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET`
- `EXAM_SYS_NEXT_TOKEN_ALGORITHM`
- `EXAM_SYS_NEXT_ACCESS_TOKEN_EXPIRES_MINUTES`
- `EXAM_SYS_NEXT_REFRESH_TOKEN_EXPIRES_MINUTES`
- `EXAM_SYS_NEXT_CORS_ALLOWED_ORIGINS`

Worker required baseline:
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_SSLMODE`
- `WORKER_POLL_INTERVAL_SECONDS`
- `WORKER_IDLE_SLEEP_SECONDS`
- `WORKER_BATCH_SIZE`
- `WORKER_LEASE_SECONDS`
- `WORKER_MAX_RETRIES`
- `WORKER_RETRY_BACKOFF_SECONDS`
- `WORKER_LOG_LEVEL`

Maintenance required:
- `POSTGRES_MAINTENANCE_HOST`
- `POSTGRES_MAINTENANCE_PORT`
- `POSTGRES_MAINTENANCE_DB`
- `POSTGRES_MAINTENANCE_USER`
- `POSTGRES_MAINTENANCE_PASSWORD`
- `POSTGRES_MAINTENANCE_SSLMODE`

Frontend required:
- `VITE_API_BASE_URL`

LAN-specific guidance:
- API/Frontend base URLs must point to LAN-reachable server endpoint, not localhost, for client devices.
- Do not commit `.env` files.
- Keep secrets out of logs and reports.
- Store secrets outside Git (for example local password manager or server admin vault).
- Hosted/staging DB integration is not applicable for LAN-only deployment.
- No cloud/production deployment claim is made in this LAN plan.
- Operators can still run individual scripts manually for troubleshooting.

## 7. LAN Blockers Inventory

1. API binding host blocker:
- Current rehearsals bind API to `127.0.0.1`.
- LAN clients require `0.0.0.0` binding plus firewall allow rules.

2. Frontend API base URL blocker:
- Current defaults use localhost loopback.
- LAN clients require frontend built/run with LAN server API URL.

3. CORS/origin blocker:
- API default CORS origins include localhost only.
- LAN client origins must be explicitly included in `EXAM_SYS_NEXT_CORS_ALLOWED_ORIGINS`.

4. Worker env completeness blocker:
- Worker loop controls and DB env contract must be fully set before long-running runtime loops.

5. PostgreSQL local access blocker:
- PostgreSQL must accept intended local/LAN connections based on deployment policy.
- Runtime vs maintenance role separation must remain enforced.

6. Firewall blocker:
- Required ports must be opened in LAN policy (API/frontend) and DB restricted appropriately.

7. Result polling readiness blocker:
- End-to-end route requires API polling endpoint reachable and worker pipelines processing jobs.

## 8. LAN Health Check Plan

Server-side checks:
1. API health returns success envelope.
2. API DB health confirms DB reachability.
3. Worker config-check passes (`--role all`).
4. DB release smokes 276-280 pass.

Client-side checks (from another LAN device):
1. Frontend route reachable over LAN URL.
2. Login/auth flow works.
3. Submission result page loads and polls processing status.
4. Non-owner access restrictions still enforced.

Addressing rule reminders:
- API must be reachable from LAN clients at `http://<SERVER_LAN_IP>:8000`.
- Frontend must call API through `VITE_API_BASE_URL` using LAN server IP.
- Browser-side `127.0.0.1` always points to the client machine, not the LAN server.

## 9. LAN E2E Scenario List

Minimum LAN E2E scenarios:
1. Client login and session establishment.
2. Submit/seal flow visible on frontend.
3. Processing status polling (`/processing-status`) transitions until terminal state.
4. Completed result rendering with expected score summary.
5. Access-control scenario: non-owner cannot read owner submission result.

## 10. Backup/Restore Operational Note

Status retained:
- Local backup/restore drill remains PASS.

Operational boundary:
- Continue using maintenance role for backup/restore and smoke operations only.
- Keep runtime role for API/worker runtime.
- Do not include raw backup artifacts in commits.

## 11. Security Boundaries

- Do not expose passwords, DSNs, tokens, sealed answers, raw SQL answers, or capture payloads.
- Do not weaken verification checkers or smoke SQL.
- Do not claim cloud/production readiness from this LAN-only plan.
- Keep hosted/staging integration docs; mark them not applicable/pending for LAN mode.

Firewall notes:
- Allow inbound API port on the LAN server.
- Allow inbound frontend port on the LAN server.
- Keep PostgreSQL port server-local unless explicit client access is required.

Non-secret logging rules:
- Operator scripts must avoid printing passwords, DSNs, or token values.
- Evidence collection must remain sanitized.

## 12. Done vs Pending

Done:
- Local hardening checkers in place and passing.
- Local backup/restore drill evidence PASS.
- Hosted checker gate (`run_db_integration=false`) PASS evidence exists.

Pending for LAN deployment readiness:
- LAN host binding and firewall hardening execution.
- LAN-specific env value finalization (API URL/CORS/frontend base URL).
- LAN runbook execution evidence with client-device validation.
- Hosted/staging DB integration remains pending/not-applicable for current LAN-only model.

## 13. Next Prompts

LAN-2 (implementation and LAN bind/config update prompt):
- "Apply LAN runtime configuration updates (bind API/frontend for LAN, set CORS and frontend API base URL via env placeholders), keep security invariants, and produce a LAN startup command pack without secrets."

LAN-4 (execution and evidence prompt):
- "Execute LAN runtime rehearsal on server and one client device, capture sanitized browser E2E and health evidence, and update readiness reporting with LAN-only pass/fail and explicit non-claims."
