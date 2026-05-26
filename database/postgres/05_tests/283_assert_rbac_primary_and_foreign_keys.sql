-- Verifies RBAC primary keys and foreign keys.

DO
$$
DECLARE
    v_pk_count integer;
BEGIN
    SELECT count(*)
    INTO v_pk_count
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'identity'
      AND c.contype = 'p'
      AND t.relname IN ('permission', 'role_permission');

    IF v_pk_count <> 2 THEN
        RAISE EXCEPTION 'Expected PK on identity.permission and identity.role_permission, found %', v_pk_count;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'identity'
          AND t.relname = 'role_permission'
          AND c.contype = 'f'
          AND c.conname = 'fk_identity_role_permission_role'
    ) THEN
        RAISE EXCEPTION 'Missing FK fk_identity_role_permission_role';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'identity'
          AND t.relname = 'role_permission'
          AND c.contype = 'f'
          AND c.conname = 'fk_identity_role_permission_permission'
    ) THEN
        RAISE EXCEPTION 'Missing FK fk_identity_role_permission_permission';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'identity'
          AND t.relname = 'role_permission'
          AND c.contype = 'f'
          AND c.conname = 'fk_identity_role_permission_granted_by'
    ) THEN
        RAISE EXCEPTION 'Missing FK fk_identity_role_permission_granted_by';
    END IF;

    RAISE NOTICE 'PASS: RBAC primary keys and foreign keys are correct.';
END
$$;
