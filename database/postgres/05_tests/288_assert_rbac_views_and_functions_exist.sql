-- Verifies RBAC helper views and functions exist.

DO
$$
DECLARE
    v_has_permission_fn regprocedure;
    v_has_any_permission_fn regprocedure;
BEGIN
    IF to_regclass('identity.v_role_permission_matrix') IS NULL THEN
        RAISE EXCEPTION 'View identity.v_role_permission_matrix does not exist';
    END IF;

    IF to_regclass('identity.v_user_effective_permission') IS NULL THEN
        RAISE EXCEPTION 'View identity.v_user_effective_permission does not exist';
    END IF;

    v_has_permission_fn := to_regprocedure('identity.has_permission(bigint,character varying)');
    IF v_has_permission_fn IS NULL THEN
        RAISE EXCEPTION 'Function identity.has_permission(bigint, varchar) does not exist';
    END IF;

    v_has_any_permission_fn := to_regprocedure('identity.has_any_permission(bigint,character varying[])');
    IF v_has_any_permission_fn IS NULL THEN
        RAISE EXCEPTION 'Function identity.has_any_permission(bigint, varchar[]) does not exist';
    END IF;

    RAISE NOTICE 'PASS: RBAC helper views and functions exist.';
END
$$;
