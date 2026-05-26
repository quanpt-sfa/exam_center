-- Verifies RBAC base tables exist.

DO
$$
BEGIN
    IF to_regclass('identity.permission') IS NULL THEN
        RAISE EXCEPTION 'Table identity.permission does not exist';
    END IF;

    IF to_regclass('identity.role_permission') IS NULL THEN
        RAISE EXCEPTION 'Table identity.role_permission does not exist';
    END IF;

    RAISE NOTICE 'PASS: RBAC tables exist.';
END
$$;
