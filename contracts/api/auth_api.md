# Auth API Foundation (Greenfield FastAPI)

## Scope
This auth foundation applies only to the greenfield FastAPI service under `backend`.

It does not modify legacy Flask runtime or legacy SQL Server access.

## Endpoints
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/refresh`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/change-password`

## Login behavior
- Accepts identifier (`username` or `email`) plus password.
- Uses generic invalid credential message to avoid leaking whether username/email exists.
- Records persisted login attempt audit rows for both success and failure in `identity.login_attempt`.
- Applies basic PostgreSQL-backed rate limiting and lockout checks by normalized identifier (and IP when present).
- Keeps public lockout response generic (`401 invalid_credentials`) to avoid signaling lockout/user-existence state.
- Rejects inactive users (`user_status` not `ACTIVE`).
- Returns access token and refresh token.
- Creates one persisted refresh session row in `identity.user_session`.

## RBAC projection
`GET /api/v1/auth/me` returns:
- `user_id`
- `username`
- `email`
- `display_name` (from `identity.person.full_name`)
- `roles` (from `identity.user_role` + `identity.role`)
- `permissions` (effective active permissions from `identity.permission` via role mapping)
- `active`

## Authorization data model

- `identity.role` + `identity.user_role`: role assignment layer (user nào có role nào).
- `identity.permission` + `identity.role_permission`: function-level authorization layer (role nào có quyền chức năng nào).

Authorization flow:

```text
identity.app_user
	-> identity.user_role
	-> identity.role
	-> identity.role_permission
	-> identity.permission

Super-admin expansion:

```text
identity.role.is_super_admin = true
  -> role automatically has every active identity.permission
  -> no explicit identity.role_permission row needed for newly added active permission
```
```

Baseline role codes:

- `STUDENT`
- `INSTRUCTOR`
- `ADMIN`
- `ACADEMIC_OFFICER`
- `PROCTOR`
- `GRADER`

Permission-code naming convention:

- lowercase dot notation
- `module.action`
- examples: `exam.submit`, `grading.grade`, `system.configure`

## Backend authorization enforcement

Backend must enforce authorization on protected operations by one of:

- `identity.has_permission(user_id, permission_code)`
- query `identity.v_user_effective_permission`

Security rule:

- Never rely only on frontend menu/button hiding for protection.

## Frontend authorization usage

Frontend should:

- Use permissions from `auth/me` to render menus and action buttons.
- Hide actions user cannot execute.

Frontend must not:

- Treat UI hiding as final enforcement.
- Hard-code only `role_code` checks for function-level authorization.

## Baseline role-permission matrix (rút gọn)

| Role | Permission baseline |
|---|---|
| STUDENT | exam.submit, submission.view_own |
| INSTRUCTOR | question.create, grading.grade |
| ADMIN | all permissions |

## Super-admin semantics

- `ADMIN` is seeded with `identity.role.is_super_admin = true`.
- Any active permission added in the future is automatically effective for users who have active `ADMIN` role assignment.
- Non-super-admin roles (for example `STUDENT`, `INSTRUCTOR`) keep explicit `role_permission` mapping behavior.
- `identity.has_permission(user_id, permission_code)` returns `false` when:
	- user is not `ACTIVE`
	- permission does not exist
	- permission exists but `is_active=false`
- `identity.v_user_effective_permission` and `identity.v_role_permission_matrix` include virtual rows for super-admin roles while preserving regular role mappings.

## Token settings
Tokens are controlled by environment variables:
- `EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET`
- `EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET`
- `EXAM_SYS_NEXT_TOKEN_ALGORITHM`
- `EXAM_SYS_NEXT_ACCESS_TOKEN_EXPIRES_MINUTES`
- `EXAM_SYS_NEXT_REFRESH_TOKEN_EXPIRES_MINUTES`
- `AUTH_MAX_FAILED_ATTEMPTS`
- `AUTH_LOCKOUT_WINDOW_SECONDS`
- `AUTH_LOCKOUT_DURATION_SECONDS`
- `AUTH_RATE_LIMIT_ENABLED`

No token secrets are hard-coded.

## Refresh Session Persistence
Refresh token/session state is persisted in PostgreSQL table `identity.user_session`.

Stored session fields include:
- `session_id`
- `user_id`
- `refresh_jti`
- `refresh_token_hash` (hash only, never raw token)
- `issued_at`, `expires_at`
- `revoked_at`, `revoke_reason`
- `replaced_by_session_id`
- `user_agent`, `ip_address`
- `created_at`, `updated_at`

Refresh validation requires all of:
- JWT refresh token signature and type are valid.
- `jti` exists in persisted session table.
- Stored `refresh_token_hash` matches presented refresh token hash.
- Session is not revoked.
- Session is not expired.
- User is still active.

Refresh rotation behavior:
- Old session is revoked with reason `ROTATED`.
- Old session links to replacement via `replaced_by_session_id`.
- New refresh session is created for the newly issued refresh token.

Logout behavior:
- Revokes current refresh session with reason `LOGOUT`.
- Revoked refresh token cannot be used again.

## Security notes
- Passwords are hashed and verified with `passlib` (`pbkdf2_sha256`).
- Passwords and tokens are not logged by auth service.
- Login attempt audit rows store username/email, actor metadata, success/failure, and failure reason only; raw passwords and raw tokens are never stored.
- Refresh token persistence stores hash only; raw refresh token is not stored.
- TODO: add device/session management UI and endpoint set for user-visible session inventory/revocation.
