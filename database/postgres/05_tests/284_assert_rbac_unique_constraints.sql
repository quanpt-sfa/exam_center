-- Verifies RBAC unique constraints.

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'identity'
          AND t.relname = 'permission'
          AND c.contype = 'u'
          AND c.conname = 'uq_identity_permission_permission_code'
    ) THEN
        RAISE EXCEPTION 'Missing unique constraint uq_identity_permission_permission_code';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'identity'
          AND t.relname = 'role_permission'
          AND c.contype = 'u'
          AND c.conname = 'uq_identity_role_permission_role_permission'
    ) THEN
        RAISE EXCEPTION 'Missing unique constraint uq_identity_role_permission_role_permission';
    END IF;

    RAISE NOTICE 'PASS: RBAC unique constraints are correct.';
END
$$;
