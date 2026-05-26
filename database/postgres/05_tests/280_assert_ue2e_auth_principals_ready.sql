-- Verifies readiness for UE2E canonical auth-principal seeding and bearer-token scenarios.

DO
$$
DECLARE
    v_missing_tables text;
    v_missing_columns text;
    v_missing_roles text;
    v_missing_uniques text;
BEGIN
    WITH required_tables AS (
        SELECT *
        FROM (VALUES
            ('identity', 'person'),
            ('identity', 'app_user'),
            ('identity', 'role'),
            ('identity', 'user_role'),
            ('identity', 'student_profile')
        ) AS t(schema_name, table_name)
    )
    SELECT string_agg(format('%s.%s', rt.schema_name, rt.table_name), ', ' ORDER BY rt.schema_name, rt.table_name)
    INTO v_missing_tables
    FROM required_tables rt
    LEFT JOIN information_schema.tables it
        ON it.table_schema = rt.schema_name
       AND it.table_name = rt.table_name
    WHERE it.table_name IS NULL;

    IF v_missing_tables IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required identity tables for UE2E auth principals: %', v_missing_tables;
    END IF;

    WITH required_columns AS (
        SELECT *
        FROM (VALUES
            ('identity', 'app_user', 'user_id'),
            ('identity', 'app_user', 'person_id'),
            ('identity', 'app_user', 'username'),
            ('identity', 'app_user', 'email_login'),
            ('identity', 'app_user', 'password_hash'),
            ('identity', 'app_user', 'user_status'),
            ('identity', 'person', 'person_id'),
            ('identity', 'person', 'full_name'),
            ('identity', 'person', 'person_status'),
            ('identity', 'role', 'role_id'),
            ('identity', 'role', 'role_code'),
            ('identity', 'user_role', 'user_id'),
            ('identity', 'user_role', 'role_id'),
            ('identity', 'user_role', 'is_active'),
            ('identity', 'student_profile', 'student_id'),
            ('identity', 'student_profile', 'person_id'),
            ('identity', 'student_profile', 'student_code'),
            ('identity', 'student_profile', 'student_status')
        ) AS t(schema_name, table_name, column_name)
    )
    SELECT string_agg(format('%s.%s.%s', rc.schema_name, rc.table_name, rc.column_name), ', ' ORDER BY rc.schema_name, rc.table_name, rc.column_name)
    INTO v_missing_columns
    FROM required_columns rc
    LEFT JOIN information_schema.columns c
        ON c.table_schema = rc.schema_name
       AND c.table_name = rc.table_name
       AND c.column_name = rc.column_name
    WHERE c.column_name IS NULL;

    IF v_missing_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required identity columns for UE2E auth principals: %', v_missing_columns;
    END IF;

    WITH required_roles AS (
        SELECT *
        FROM (VALUES ('ADMIN'), ('STUDENT')) AS t(role_code)
    )
    SELECT string_agg(rr.role_code, ', ' ORDER BY rr.role_code)
    INTO v_missing_roles
    FROM required_roles rr
    LEFT JOIN identity.role r ON r.role_code = rr.role_code
    WHERE r.role_id IS NULL;

    IF v_missing_roles IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required identity.role entries for UE2E auth principals: %', v_missing_roles;
    END IF;

    WITH required_uniques AS (
        SELECT *
        FROM (VALUES
            ('identity', 'app_user', 'username'),
            ('identity', 'student_profile', 'student_code')
        ) AS t(schema_name, table_name, column_name)
    )
    SELECT string_agg(format('%s.%s(%s)', ru.schema_name, ru.table_name, ru.column_name), ', ' ORDER BY ru.schema_name, ru.table_name, ru.column_name)
    INTO v_missing_uniques
    FROM required_uniques ru
    WHERE NOT EXISTS (
        SELECT 1
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        JOIN pg_attribute att ON att.attrelid = rel.oid
        WHERE con.contype = 'u'
          AND nsp.nspname = ru.schema_name
          AND rel.relname = ru.table_name
          AND att.attnum = ANY(con.conkey)
          AND att.attname = ru.column_name
    );

    IF v_missing_uniques IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required unique constraints for UE2E auth principals: %', v_missing_uniques;
    END IF;

    RAISE NOTICE 'PASS: UE2E auth principal seed readiness checks are satisfied.';
END
$$;
