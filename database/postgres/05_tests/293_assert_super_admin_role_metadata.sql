-- Verifies super-admin role metadata columns and seeded values.

DO
$$
DECLARE
    v_has_is_super_admin boolean;
    v_has_is_active boolean;
    v_admin_is_super_admin boolean;
    v_student_is_super_admin boolean;
BEGIN
    IF to_regclass('identity.roles') IS NOT NULL THEN
        RAISE EXCEPTION 'Unexpected duplicate table identity.roles exists';
    END IF;

    IF to_regclass('identity.user_roles') IS NOT NULL THEN
        RAISE EXCEPTION 'Unexpected duplicate table identity.user_roles exists';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'identity'
          AND table_name = 'role'
          AND column_name = 'is_super_admin'
    ) INTO v_has_is_super_admin;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'identity'
          AND table_name = 'role'
          AND column_name = 'is_active'
    ) INTO v_has_is_active;

    IF v_has_is_super_admin IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'identity.role.is_super_admin column is required';
    END IF;

    IF v_has_is_active IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'identity.role.is_active column is required';
    END IF;

    SELECT bool_or(is_super_admin)
    INTO v_admin_is_super_admin
    FROM identity.role
    WHERE role_code = 'ADMIN';

    IF v_admin_is_super_admin IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'ADMIN must be is_super_admin=true';
    END IF;

    SELECT bool_or(is_super_admin)
    INTO v_student_is_super_admin
    FROM identity.role
    WHERE role_code = 'STUDENT';

    IF v_student_is_super_admin IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'STUDENT must be is_super_admin=false';
    END IF;

    RAISE NOTICE 'PASS: Super-admin role metadata and seed values are correct.';
END
$$;