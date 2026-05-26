-- Verifies RBAC check constraints.

DO
$$
DECLARE
    v_missing_checks text;
BEGIN
    WITH expected_constraints AS (
        SELECT *
        FROM (VALUES
            ('identity', 'permission', 'ck_identity_permission_permission_code_not_blank'),
            ('identity', 'permission', 'ck_identity_permission_module_code_not_blank'),
            ('identity', 'permission', 'ck_identity_permission_action_code_not_blank'),
            ('identity', 'permission', 'ck_identity_permission_permission_name_not_blank'),
            ('identity', 'permission', 'ck_identity_permission_updated_at'),
            ('identity', 'role', 'ck_identity_role_updated_at')
        ) AS t(schema_name, table_name, constraint_name)
    )
    SELECT string_agg(ec.constraint_name, ', ' ORDER BY ec.constraint_name)
    INTO v_missing_checks
    FROM expected_constraints ec
    LEFT JOIN pg_constraint c
        ON c.conname = ec.constraint_name
    LEFT JOIN pg_class t
        ON t.oid = c.conrelid
    LEFT JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE c.oid IS NULL
       OR n.nspname <> ec.schema_name
       OR t.relname <> ec.table_name;

    IF v_missing_checks IS NOT NULL THEN
        RAISE EXCEPTION 'Missing RBAC check constraints: %', v_missing_checks;
    END IF;

    RAISE NOTICE 'PASS: RBAC check constraints are correct.';
END
$$;
