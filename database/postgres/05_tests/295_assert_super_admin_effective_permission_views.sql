-- Verifies effective permission views include super-admin virtual permissions.

BEGIN;

DO
$$
DECLARE
    v_suffix text := txid_current()::text;
    v_admin_user_id bigint;
    v_student_user_id bigint;
    v_admin_role_id bigint;
    v_student_role_id bigint;
    v_admin_person_id bigint;
    v_student_person_id bigint;
    v_exists boolean;
    v_admin_matrix_count integer;
BEGIN
    SELECT role_id INTO v_admin_role_id FROM identity.role WHERE role_code = 'ADMIN' AND is_active = true;
    SELECT role_id INTO v_student_role_id FROM identity.role WHERE role_code = 'STUDENT' AND is_active = true;

    IF v_admin_role_id IS NULL OR v_student_role_id IS NULL THEN
        RAISE EXCEPTION 'Required roles ADMIN/STUDENT must exist and be active';
    END IF;

    INSERT INTO identity.permission (permission_code, module_code, action_code, permission_name, description, is_active)
    VALUES ('test.view_future_feature', 'test', 'view_future_feature', 'Test View Future Feature', 'Permission for view semantics smoke test', true)
    ON CONFLICT (permission_code) DO UPDATE
    SET
        module_code = EXCLUDED.module_code,
        action_code = EXCLUDED.action_code,
        permission_name = EXCLUDED.permission_name,
        description = EXCLUDED.description,
        is_active = true,
        updated_at = now();

    INSERT INTO identity.person (
        full_name,
        person_status
    )
    VALUES (
        'Admin View Smoke ' || v_suffix,
        'ACTIVE'
    )
    RETURNING person_id INTO v_admin_person_id;

    INSERT INTO identity.person (
        full_name,
        person_status
    )
    VALUES (
        'Student View Smoke ' || v_suffix,
        'ACTIVE'
    )
    RETURNING person_id INTO v_student_person_id;

    INSERT INTO identity.app_user (
        person_id,
        username,
        email_login,
        password_hash,
        user_status
    )
    VALUES
        (v_admin_person_id, 'admin_view_smoke_' || v_suffix, 'admin_view_smoke_' || v_suffix || '@local.test', 'hash', 'ACTIVE'),
        (v_student_person_id, 'student_view_smoke_' || v_suffix, 'student_view_smoke_' || v_suffix || '@local.test', 'hash', 'ACTIVE');

    SELECT user_id INTO v_admin_user_id FROM identity.app_user WHERE username = 'admin_view_smoke_' || v_suffix;
    SELECT user_id INTO v_student_user_id FROM identity.app_user WHERE username = 'student_view_smoke_' || v_suffix;

    INSERT INTO identity.user_role (user_id, role_id, assigned_at, is_active)
    VALUES
        (v_admin_user_id, v_admin_role_id, now(), true),
        (v_student_user_id, v_student_role_id, now(), true);

    SELECT EXISTS (
        SELECT 1
        FROM identity.v_user_effective_permission v
        WHERE v.user_id = v_admin_user_id
          AND v.role_code = 'ADMIN'
          AND v.permission_code = 'test.view_future_feature'
    ) INTO v_exists;

    IF v_exists IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'v_user_effective_permission must include super-admin virtual permission for ADMIN user';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM identity.v_user_effective_permission v
        WHERE v.user_id = v_student_user_id
          AND v.role_code = 'STUDENT'
          AND v.permission_code = 'test.view_future_feature'
    ) INTO v_exists;

    IF v_exists IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'v_user_effective_permission must not grant new permission to STUDENT user';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM identity.v_role_permission_matrix m
        WHERE m.role_code = 'ADMIN'
          AND m.permission_code = 'test.view_future_feature'
    ) INTO v_exists;

    IF v_exists IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'v_role_permission_matrix must include super-admin virtual permission for ADMIN';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM identity.v_role_permission_matrix m
        WHERE m.role_code = 'STUDENT'
          AND m.permission_code = 'test.view_future_feature'
    ) INTO v_exists;

    IF v_exists IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'v_role_permission_matrix must not include new permission for STUDENT';
    END IF;

    SELECT count(*)
    INTO v_admin_matrix_count
    FROM identity.v_role_permission_matrix m
    WHERE m.role_code = 'ADMIN'
      AND m.permission_code = 'test.view_future_feature';

    IF v_admin_matrix_count <> 1 THEN
        RAISE EXCEPTION 'Expected exactly one ADMIN row for test.view_future_feature in v_role_permission_matrix, found %', v_admin_matrix_count;
    END IF;

    RAISE NOTICE 'PASS: Super-admin effective permission views are correct.';
END
$$;

ROLLBACK;