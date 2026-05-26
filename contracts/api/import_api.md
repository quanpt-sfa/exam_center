# Import API

## Scope
The Import API provides a controlled staging-first workflow for CSV/XLSX ingestion.

MVP templates:
- STUDENT_V1
- ENROLLMENT_V1

No domain writes occur during upload/parse/validate. Domain writes are executed only by commit.

## Base Path
/api/v1/imports

## Authentication and Authorization
All endpoints require an authenticated access token.

Permission mapping:
- imports:read: status, templates, template detail, preview, errors, audit
- imports:write: create job, upload, parse, validate
- imports:commit: commit and rollback

The permission layer is fail-closed. Missing authentication returns unauthorized. Missing permission returns permission_denied.

## Actor Derivation Rule
Actor identity is always derived from the authenticated principal.

Rules:
- actor_user_id is server-derived from current_user.user_id.
- actor_agent is server-derived from authenticated principal identity (username/email when available).
- Client-controlled actor_user_id is rejected from request payload (validation error).

Reason for rejecting client actor_user_id:
- Prevent identity spoofing in importing.import_job, importing.import_commit, importing.import_audit_event, and ops command-run records.
- Preserve audit trace integrity by ensuring the actor source of truth is the access token principal.

## Endpoints
- GET /status
- GET /templates
- GET /templates/{template_code}
- POST /jobs
- POST /jobs/{job_id}/upload
- POST /jobs/{job_id}/parse
- POST /jobs/{job_id}/validate
- GET /jobs/{job_id}/preview
- POST /jobs/{job_id}/commit
- POST /jobs/{job_id}/rollback
- GET /jobs/{job_id}/errors
- GET /jobs/{job_id}/audit

## Workflow
1. Create job with template_code.
2. Upload file.
3. Parse file to importing.import_row_staging.
4. Validate rows and inspect errors.
5. Preview rows and counters (optional).
6. Commit validated rows.

## Audit and Safety
- Import events are written to importing.import_audit_event.
- Command runs/events are written to ops.agent_command_run and ops.agent_command_event.
- Commit requires explicit API call; validate and preview never auto-commit.
- Commit uses a single transaction boundary for domain writes, import metadata updates, and ops/audit events. If any row commit step fails, the entire commit rolls back and no partial domain/entity-link writes are persisted.

## Template Notes
STUDENT_V1 required columns:
- student_code
- full_name

STUDENT_V1 optional columns:
- program_id
- cohort
- entry_year
- student_status (default ACTIVE)
- person_status (default ACTIVE)

STUDENT_V1 commit target entities:
- identity.person
- identity.student_profile

ENROLLMENT_V1 required columns:
- class_section_id
- student_id

ENROLLMENT_V1 optional columns:
- enrollment_status (default ENROLLED)
- note

ENROLLMENT_V1 commit target entity:
- academic.class_enrollment
