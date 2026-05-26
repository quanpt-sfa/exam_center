-- Add super-admin role semantics so ADMIN automatically has all active permissions.

ALTER TABLE IF EXISTS identity.role
    ADD COLUMN IF NOT EXISTS is_super_admin boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NULL;

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'identity'
          AND t.relname = 'role'
          AND c.conname = 'ck_identity_role_updated_at'
    ) THEN
        ALTER TABLE identity.role
            ADD CONSTRAINT ck_identity_role_updated_at
            CHECK (updated_at IS NULL OR updated_at >= created_at);
    END IF;
END
$$;

COMMENT ON COLUMN identity.role.is_super_admin IS
    'True means role automatically grants all active permissions without explicit role_permission rows.';

DO
$$
DECLARE
    missing_roles text;
BEGIN
    SELECT string_agg(expected_role, ', ' ORDER BY expected_role)
    INTO missing_roles
    FROM (
        SELECT unnest(
            ARRAY['STUDENT', 'INSTRUCTOR', 'ADMIN', 'ACADEMIC_OFFICER', 'PROCTOR', 'GRADER']
        ) AS expected_role
    ) src
    WHERE NOT EXISTS (
        SELECT 1
        FROM identity.role r
        WHERE r.role_code = src.expected_role
    );

    IF missing_roles IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required roles for super-admin seed: %', missing_roles;
    END IF;

    UPDATE identity.role
    SET
        is_super_admin = (role_code = 'ADMIN'),
        updated_at = now()
    WHERE role_code IN ('STUDENT', 'INSTRUCTOR', 'ADMIN', 'ACADEMIC_OFFICER', 'PROCTOR', 'GRADER')
      AND COALESCE(is_super_admin, false) IS DISTINCT FROM (role_code = 'ADMIN');
END
$$;

CREATE OR REPLACE VIEW identity.v_role_permission_matrix AS
SELECT
    r.role_code,
    r.role_name,
    p.permission_code,
    p.module_code,
    p.action_code,
    p.permission_name,
    r.is_active AS role_is_active,
    p.is_active AS permission_is_active,
    true AS role_permission_is_active
FROM identity.role r
JOIN identity.permission p
    ON p.is_active = true
WHERE r.is_active = true
  AND r.is_super_admin = true

UNION

SELECT
    r.role_code,
    r.role_name,
    p.permission_code,
    p.module_code,
    p.action_code,
    p.permission_name,
    r.is_active AS role_is_active,
    p.is_active AS permission_is_active,
    rp.is_active AS role_permission_is_active
FROM identity.role_permission rp
JOIN identity.role r
    ON r.role_id = rp.role_id
JOIN identity.permission p
    ON p.permission_id = rp.permission_id
WHERE r.is_active = true
  AND p.is_active = true
  AND rp.is_active = true;

COMMENT ON VIEW identity.v_role_permission_matrix IS
    'Active role-permission matrix. Super-admin roles are expanded to all active permissions without requiring physical role_permission rows.';

CREATE OR REPLACE VIEW identity.v_user_effective_permission AS
SELECT
    u.user_id,
    u.username,
    u.user_status,
    r.role_code,
    p.permission_code,
    p.module_code,
    p.action_code,
    p.permission_name
FROM identity.app_user u
JOIN identity.user_role ur
    ON ur.user_id = u.user_id
JOIN identity.role r
    ON r.role_id = ur.role_id
JOIN identity.permission p
    ON p.is_active = true
WHERE upper(coalesce(u.user_status, '')) = 'ACTIVE'
  AND ur.is_active = true
  AND r.is_active = true
  AND r.is_super_admin = true

UNION

SELECT
    u.user_id,
    u.username,
    u.user_status,
    r.role_code,
    p.permission_code,
    p.module_code,
    p.action_code,
    p.permission_name
FROM identity.app_user u
JOIN identity.user_role ur
    ON ur.user_id = u.user_id
JOIN identity.role r
    ON r.role_id = ur.role_id
JOIN identity.role_permission rp
    ON rp.role_id = r.role_id
JOIN identity.permission p
    ON p.permission_id = rp.permission_id
WHERE upper(coalesce(u.user_status, '')) = 'ACTIVE'
  AND ur.is_active = true
  AND r.is_active = true
  AND rp.is_active = true
  AND p.is_active = true;

COMMENT ON VIEW identity.v_user_effective_permission IS
    'Effective active permissions per active user. Super-admin roles contribute all active permissions automatically.';

CREATE OR REPLACE FUNCTION identity.has_permission(
    p_user_id bigint,
    p_permission_code varchar
)
RETURNS boolean
LANGUAGE sql
STABLE
SET search_path = identity, pg_temp
AS
$$
    SELECT
        CASE
            WHEN p_user_id IS NULL
                 OR p_permission_code IS NULL
                 OR length(trim(p_permission_code)) = 0
                THEN false
            ELSE EXISTS (
                WITH requested_permission AS (
                    SELECT p.permission_id
                    FROM identity.permission p
                    WHERE lower(p.permission_code) = lower(trim(p_permission_code))
                      AND p.is_active = true
                ),
                active_user AS (
                    SELECT u.user_id
                    FROM identity.app_user u
                    WHERE u.user_id = p_user_id
                      AND upper(coalesce(u.user_status, '')) = 'ACTIVE'
                ),
                active_roles AS (
                    SELECT DISTINCT r.role_id, r.is_super_admin
                    FROM identity.user_role ur
                    JOIN identity.role r
                        ON r.role_id = ur.role_id
                    JOIN active_user au
                        ON au.user_id = ur.user_id
                    WHERE ur.is_active = true
                      AND r.is_active = true
                )
                SELECT 1
                FROM requested_permission rp
                JOIN active_roles ar
                    ON true
                LEFT JOIN identity.role_permission rpm
                    ON rpm.role_id = ar.role_id
                   AND rpm.permission_id = rp.permission_id
                   AND rpm.is_active = true
                WHERE ar.is_super_admin = true
                   OR rpm.role_permission_id IS NOT NULL
            )
        END;
$$;

COMMENT ON FUNCTION identity.has_permission(bigint, varchar) IS
    'Returns true only when active user has active permission via active role_permission or via active super-admin role.';

CREATE OR REPLACE FUNCTION identity.has_any_permission(
    p_user_id bigint,
    p_permission_codes varchar[]
)
RETURNS boolean
LANGUAGE sql
STABLE
SET search_path = identity, pg_temp
AS
$$
    SELECT
        CASE
            WHEN p_user_id IS NULL
                 OR p_permission_codes IS NULL
                 OR cardinality(p_permission_codes) = 0
                THEN false
            ELSE EXISTS (
                SELECT 1
                FROM unnest(p_permission_codes) AS c(permission_code)
                WHERE c.permission_code IS NOT NULL
                  AND length(trim(c.permission_code)) > 0
                  AND identity.has_permission(p_user_id, c.permission_code)
            )
        END;
$$;

COMMENT ON FUNCTION identity.has_any_permission(bigint, varchar[]) IS
    'Returns true when active user has at least one requested active permission, including via super-admin role.';

DO
$$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_app') THEN
        GRANT SELECT ON TABLE identity.v_role_permission_matrix TO exam_sys_app;
        GRANT SELECT ON TABLE identity.v_user_effective_permission TO exam_sys_app;
        GRANT EXECUTE ON FUNCTION identity.has_permission(bigint, varchar) TO exam_sys_app;
        GRANT EXECUTE ON FUNCTION identity.has_any_permission(bigint, varchar[]) TO exam_sys_app;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_readonly') THEN
        GRANT SELECT ON TABLE identity.v_role_permission_matrix TO exam_sys_readonly;
        GRANT SELECT ON TABLE identity.v_user_effective_permission TO exam_sys_readonly;
    END IF;
END
$$;

REVOKE ALL ON TABLE identity.v_role_permission_matrix FROM PUBLIC;
REVOKE ALL ON TABLE identity.v_user_effective_permission FROM PUBLIC;
REVOKE ALL ON FUNCTION identity.has_permission(bigint, varchar) FROM PUBLIC;
REVOKE ALL ON FUNCTION identity.has_any_permission(bigint, varchar[]) FROM PUBLIC;