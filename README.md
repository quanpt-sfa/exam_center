# Exam Center Standalone

Minimal local development scaffold for the standalone workspace.

## Prerequisites

- Docker Desktop with `docker compose`
- Python 3.12 for local backend and worker commands
- Node.js 20 for local frontend commands

## Safety

- Use only local placeholder credentials.
- Do not point these commands at a production-like database.
- This scaffold does not run migrations, resets, or seed scripts automatically.

## Start The Dev Stack

```powershell
docker compose -f docker-compose.dev.yml up
```

Services:

- frontend: [http://localhost:5173](http://localhost:5173)
- backend: [http://localhost:8001](http://localhost:8001)
- postgres: `localhost:5432`

The compose file uses unsafe local placeholders only:

- `POSTGRES_PASSWORD=postgres`
- `EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET=dev-only-change-me`
- `EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET=dev-only-change-me`

## Stop The Dev Stack

```powershell
docker compose -f docker-compose.dev.yml down
```

Add `-v` only if you intentionally want to remove the local Postgres volume.

## Manual Database Safety Check

Before any manual schema setup, verify the target database is still test-only:

```powershell
$env:POSTGRES_DB="exam_sys_test"
python database/postgres/scripts/check_test_db_target.py
```

Schema setup remains an explicit manual step. This scaffold does not run destructive database scripts on startup.

## Run Tests

```powershell
.venv/Scripts/python -m pytest backend/tests -q
cd frontend
npm test -- --run
cd ..
$env:PYTHONPATH="$PWD\backend;$PWD\worker"
.venv/Scripts/python -m pytest worker/tests -q
```

## Run Services Manually

Backend:

```powershell
$env:PYTHONPATH="$PWD\backend"
$env:ENVIRONMENT="development"
$env:POSTGRES_HOST="localhost"
$env:POSTGRES_PORT="5432"
$env:POSTGRES_DB="exam_sys_test"
$env:POSTGRES_USER="postgres"
$env:POSTGRES_PASSWORD="postgres"
$env:EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET="dev-only-change-me"
$env:EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET="dev-only-change-me"
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8001
```

Frontend:

```powershell
cd frontend
$env:VITE_API_BASE_URL="http://localhost:8001"
npm ci
npm run dev -- --host 0.0.0.0 --port 5173
```

Worker:

```powershell
$env:PYTHONPATH="$PWD\backend;$PWD\worker"
$env:POSTGRES_HOST="localhost"
$env:POSTGRES_PORT="5432"
$env:POSTGRES_DB="exam_sys_test"
$env:POSTGRES_USER="postgres"
$env:POSTGRES_PASSWORD="postgres"
python -m worker_runtime.cli run-grading-worker --once --worker-id local-grading-worker
```

Worker startup is left manual because runtime mode, schema state, and queue assumptions depend on the task you are validating.
