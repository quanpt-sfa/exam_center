# Exam Center Standalone

Standalone workspace for the current Exam Center runtime and contracts.

## Architecture

- `backend/`: FastAPI backend
- `frontend/`: React + Vite frontend
- `worker/`: background worker runtime
- `database/postgres/`: PostgreSQL schema, scripts, and DB smoke assets
- `contracts/`: API, deployment, and worker-facing contracts
- `docs/`: current routing and workflow docs

## Directory Map

- `backend/app/main.py`: backend entrypoint
- `frontend/src/main.tsx`: frontend entrypoint
- `worker/worker_runtime/cli.py`: worker entrypoint
- `database/postgres/README.md`: database runtime landing
- `manifest.yaml`: agent routing manifest
- `QUICK_EDIT.md`: shortest edit path

## Quick Start

Local dev scaffold:

```powershell
docker compose -f docker-compose.dev.yml up
```

Manual backend:

```powershell
$env:PYTHONPATH="$PWD\backend"
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8001
```

Manual frontend:

```powershell
cd frontend
$env:VITE_API_BASE_URL="http://localhost:8001"
npm run dev -- --host 0.0.0.0 --port 5173
```

Manual worker:

```powershell
$env:PYTHONPATH="$PWD\backend;$PWD\worker"
python -m worker_runtime.cli run-grading-worker --once --worker-id local-grading-worker
```

## Tests

```powershell
.venv/Scripts/python -m pytest backend/tests -q
cd frontend
npm run build
npm test -- --run
cd ..
$env:PYTHONPATH="$PWD\backend;$PWD\worker"
.venv/Scripts/python -m pytest worker/tests -q
```

## CI Status

Current CI covers:

- backend tests
- frontend build and unit tests
- worker tests
- docs checkers
- backend PostgreSQL smoke
- worker PostgreSQL smoke
- frontend E2E smoke

## Environment Safety

- Do not commit `.env`, `.env.local`, or `.env.lan`.
- Use placeholder-only local secrets such as `dev-only-change-me`.
- Use only test/dev PostgreSQL targets such as `exam_sys_test`.
- No destructive DB reset or migration runs automatically from the local scaffold.

## Agent Reading Order

1. `manifest.yaml`
2. `AGENTS.md`
3. `QUICK_EDIT.md`
4. `<domain>/AGENTS.md`
5. `<domain>/README.md`
6. target file, then nearest test
