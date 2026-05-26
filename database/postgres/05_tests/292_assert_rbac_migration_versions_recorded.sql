-- Verifies RBAC migration versions are recorded in migration metadata.

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
        '0102_add_identity_permission_and_role_permission.sql',
        '0103_seed_identity_permission_catalog_and_role_mappings.sql',
        '0104_add_identity_authorization_helpers.sql',
        '0105_record_identity_rbac_versions.sql'
    );

    IF v_count <> 4 THEN
        RAISE EXCEPTION 'Expected 4 RBAC migration metadata records but found %', v_count;
    END IF;

    RAISE NOTICE 'PASS: RBAC migration metadata records exist.';
END
$$;
