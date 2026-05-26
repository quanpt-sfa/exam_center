# Ops API

## Scope
The Ops API provides authenticated operational command-run endpoints for controlled admin and agent actions.

This API guarantees atomic creation of:
- `ops.agent_command_run`
- initial `ops.agent_command_event` (`RUN_CREATED`)

Both rows are committed together or rolled back together.

## Base Path
/api/v1/ops

## Authentication and Authorization
All ops endpoints require an authenticated access token.

Permission mapping:
- ops:read: status and command-run listing
- ops:execute: create command runs

The permission layer is fail-closed.

Role fallback currently recognized for ops permissions:
- ADMIN
- AGENT
- AGENT_SERVICE
- SERVICE_ACCOUNT
- SYSTEM_AGENT

## Endpoints
- GET /status
- GET /command-runs
- POST /command-runs

## Actor Derivation Rule
Command run actor identity is derived from authenticated current_user.

Rules:
- actor_user_id is always current_user.user_id.
- actor_agent is derived from principal username/email.
- actor_user_id and actor_agent in request body are not accepted.
- Anonymous execution is not allowed.
- Service-account principals remain supported via role fallback and principal-derived actor labels.

## Transaction Semantics
`POST /command-runs` executes inside one transaction boundary:
1. verify execute permission;
2. insert command run row;
3. insert initial event row;
4. commit only when both inserts succeed.

If initial event insert fails, command run insert is rolled back (no orphan run row).

## Request/Response Notes
POST /command-runs request:
- command_code: required
- command_text: optional
- event_payload: optional object

Sensitive values in `event_payload` are redacted before persistence for keys such as password/token/secret/api-key variants.

POST /command-runs response includes:
- agent_command_run_id
- command_code
- run_status
- actor_user_id
- actor_agent

GET /command-runs supports limit/offset pagination.
