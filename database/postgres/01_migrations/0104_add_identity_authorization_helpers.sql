-- Add queryable authorization helpers for backend/frontend RBAC checks.

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
    'Active-only role-permission matrix. This view intentionally filters inactive roles, permissions, and mappings by default for operational authorization reads.';

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
    'Effective active permissions per active user through active role and role-permission links.';

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
                SELECT 1
                FROM identity.v_user_effective_permission v
                WHERE v.user_id = p_user_id
                  AND lower(v.permission_code) = lower(trim(p_permission_code))
            )
        END;
$$;

COMMENT ON FUNCTION identity.has_permission(bigint, varchar) IS
    'Returns true only when the active user has the active permission via at least one active role.';

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
                FROM identity.v_user_effective_permission v
                JOIN LATERAL unnest(p_permission_codes) AS c(permission_code)
                    ON true
                WHERE v.user_id = p_user_id
                  AND c.permission_code IS NOT NULL
                  AND length(trim(c.permission_code)) > 0
                  AND lower(v.permission_code) = lower(trim(c.permission_code))
            )
        END;
$$;

COMMENT ON FUNCTION identity.has_any_permission(bigint, varchar[]) IS
    'Returns true when the active user has at least one active permission from the provided permission-code array.';

DO
$$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_app') THEN
        GRANT SELECT ON TABLE identity.v_role_permission_matrix TO exam_sys_app;
        GRANT SELECT ON TABLE identity.v_user_effective_permission TO exam_sys_app;
        GRANT EXECUTE ON FUNCTION identity.has_permission(bigint, varchar) TO exam_sys_app;
        GRANT EXECUTE ON FUNCTION identity.has_any_permission(bigint, varchar[]) TO exam_sys_app;

        REVOKE INSERT, UPDATE, DELETE ON TABLE identity.v_role_permission_matrix FROM exam_sys_app;
        REVOKE INSERT, UPDATE, DELETE ON TABLE identity.v_user_effective_permission FROM exam_sys_app;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_readonly') THEN
        GRANT SELECT ON TABLE identity.v_role_permission_matrix TO exam_sys_readonly;
        GRANT SELECT ON TABLE identity.v_user_effective_permission TO exam_sys_readonly;

        REVOKE INSERT, UPDATE, DELETE ON TABLE identity.v_role_permission_matrix FROM exam_sys_readonly;
        REVOKE INSERT, UPDATE, DELETE ON TABLE identity.v_user_effective_permission FROM exam_sys_readonly;
    END IF;
END
$$;

REVOKE ALL ON TABLE identity.v_role_permission_matrix FROM PUBLIC;
REVOKE ALL ON TABLE identity.v_user_effective_permission FROM PUBLIC;
REVOKE ALL ON FUNCTION identity.has_permission(bigint, varchar) FROM PUBLIC;
REVOKE ALL ON FUNCTION identity.has_any_permission(bigint, varchar[]) FROM PUBLIC;
