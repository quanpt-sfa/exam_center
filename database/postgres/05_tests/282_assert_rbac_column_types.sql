-- Verifies RBAC column existence and data types.

DO
$$
DECLARE
    v_missing_or_mismatched text;
BEGIN
    WITH expected_columns AS (
        SELECT *
        FROM (VALUES
            ('identity', 'permission', 'permission_id', 'bigint', 'int8'),
            ('identity', 'permission', 'permission_code', 'character varying', 'varchar'),
            ('identity', 'permission', 'module_code', 'character varying', 'varchar'),
            ('identity', 'permission', 'action_code', 'character varying', 'varchar'),
            ('identity', 'permission', 'permission_name', 'character varying', 'varchar'),
            ('identity', 'permission', 'is_sensitive', 'boolean', 'bool'),
            ('identity', 'permission', 'is_active', 'boolean', 'bool'),
            ('identity', 'permission', 'created_at', 'timestamp with time zone', 'timestamptz'),
            ('identity', 'permission', 'updated_at', 'timestamp with time zone', 'timestamptz'),

            ('identity', 'role_permission', 'role_permission_id', 'bigint', 'int8'),
            ('identity', 'role_permission', 'role_id', 'bigint', 'int8'),
            ('identity', 'role_permission', 'permission_id', 'bigint', 'int8'),
            ('identity', 'role_permission', 'granted_at', 'timestamp with time zone', 'timestamptz'),
            ('identity', 'role_permission', 'granted_by', 'bigint', 'int8'),
            ('identity', 'role_permission', 'is_active', 'boolean', 'bool')
        ) AS t(schema_name, table_name, column_name, expected_data_type, expected_udt_name)
    )
    SELECT string_agg(
        format(
            '%s.%s.%s expected (%s/%s) got (%s/%s)',
            ec.schema_name,
            ec.table_name,
            ec.column_name,
            ec.expected_data_type,
            ec.expected_udt_name,
            coalesce(c.data_type, '<missing>'),
            coalesce(c.udt_name, '<missing>')
        ),
        ', ' ORDER BY ec.schema_name, ec.table_name, ec.column_name
    )
    INTO v_missing_or_mismatched
    FROM expected_columns ec
    LEFT JOIN information_schema.columns c
        ON c.table_schema = ec.schema_name
       AND c.table_name = ec.table_name
       AND c.column_name = ec.column_name
    WHERE c.column_name IS NULL
       OR c.data_type <> ec.expected_data_type
       OR c.udt_name <> ec.expected_udt_name;

    IF v_missing_or_mismatched IS NOT NULL THEN
        RAISE EXCEPTION 'RBAC column existence/type mismatch: %', v_missing_or_mismatched;
    END IF;

    RAISE NOTICE 'PASS: RBAC columns and data types are correct.';
END
$$;
