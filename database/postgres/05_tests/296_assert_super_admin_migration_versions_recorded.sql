-- Verifies super-admin migration versions are recorded in migration metadata.

DO
$$
DECLARE
    v_count integer;
BEGIN
    IF to_regclass('app_meta.schema_migrations') IS NULL THEN
        RAISE EXCEPTION 'app_meta.schema_migrations table is required for migration metadata assertions';
    END IF;

    SELECT COUNT(*)
    INTO v_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0106_add_identity_super_admin_role_semantics.sql',
        '0107_record_identity_super_admin_versions.sql'
    );

    IF v_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 super-admin migration metadata records but found %', v_count;
    END IF;

    RAISE NOTICE 'PASS: Super-admin migration metadata records exist.';
END
$$;