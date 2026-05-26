-- Verifies has_permission behavior for super-admin and normal users.

BEGIN;

DO
$$
DECLARE
    v_suffix text := txid_current()::text;
    v_admin_user_id bigint;
    v_student_user_id bigint;
    v_instructor_user_id bigint;
    v_disabled_admin_user_id bigint;

    v_admin_role_id bigint;
    v_student_role_id bigint;
    v_instructor_role_id bigint;

    v_admin_person_id bigint;
    v_student_person_id bigint;
    v_instructor_person_id bigint;
    v_disabled_admin_person_id bigint;

    v_result boolean;
BEGIN
    SELECT role_id INTO v_admin_role_id FROM identity.role WHERE role_code = 'ADMIN' AND is_active = true;
    SELECT role_id INTO v_student_role_id FROM identity.role WHERE role_code = 'STUDENT' AND is_active = true;
    SELECT role_id INTO v_instructor_role_id FROM identity.role WHERE role_code = 'INSTRUCTOR' AND is_active = true;

    IF v_admin_role_id IS NULL OR v_student_role_id IS NULL OR v_instructor_role_id IS NULL THEN
        RAISE EXCEPTION 'Required roles ADMIN/STUDENT/INSTRUCTOR must exist and be active';
    END IF;

    INSERT INTO identity.permission (permission_code, module_code, action_code, permission_name, description, is_active)
    VALUES ('test.future_feature', 'test', 'future_feature', 'Test Future Feature', 'Permission for super-admin behavior smoke test', true)
    ON CONFLICT (permission_code) DO UPDATE
    SET
        module_code = EXCLUDED.module_code,
        action_code = EXCLUDED.action_code,
        permission_name = EXCLUDED.permission_name,
        description = EXCLUDED.description,
        is_active = true,
        updated_at = now();

    INSERT INTO identity.permission (permission_code, module_code, action_code, permission_name, description, is_active)
    VALUES ('test.inactive_feature', 'test', 'inactive_feature', 'Test Inactive Feature', 'Inactive permission for smoke test', false)
    ON CONFLICT (permission_code) DO UPDATE
    SET
        module_code = EXCLUDED.module_code,
        action_code = EXCLUDED.action_code,
        permission_name = EXCLUDED.permission_name,
        description = EXCLUDED.description,
        is_active = false,
        updated_at = now();

    INSERT INTO identity.person (
        full_name,
        person_status
    )
    VALUES (
        'Admin Smoke ' || v_suffix,
        'ACTIVE'
    )
    RETURNING person_id INTO v_admin_person_id;

    INSERT INTO identity.person (
        full_name,
        person_status
    )
    VALUES (
        'Student Smoke ' || v_suffix,
        'ACTIVE'
    )
    RETURNING person_id INTO v_student_person_id;

    INSERT INTO identity.person (
        full_name,
        person_status
    )
    VALUES (
        'Instructor Smoke ' || v_suffix,
        'ACTIVE'
    )
    RETURNING person_id INTO v_instructor_person_id;

    INSERT INTO identity.person (
        full_name,
        person_status
    )
    VALUES (
        'Disabled Admin Smoke ' || v_suffix,
        'ACTIVE'
    )
    RETURNING person_id INTO v_disabled_admin_person_id;

    INSERT INTO identity.app_user (
        person_id,
        username,
        email_login,
        password_hash,
        user_status
    )
    VALUES
        (v_admin_person_id, 'admin_smoke_' || v_suffix, 'admin_smoke_' || v_suffix || '@local.test', 'hash', 'ACTIVE'),
        (v_student_person_id, 'student_smoke_' || v_suffix, 'student_smoke_' || v_suffix || '@local.test', 'hash', 'ACTIVE'),
        (v_instructor_person_id, 'instructor_smoke_' || v_suffix, 'instructor_smoke_' || v_suffix || '@local.test', 'hash', 'ACTIVE'),
        (v_disabled_admin_person_id, 'disabled_admin_smoke_' || v_suffix, 'disabled_admin_smoke_' || v_suffix || '@local.test', 'hash', 'DISABLED');

    SELECT user_id INTO v_admin_user_id FROM identity.app_user WHERE username = 'admin_smoke_' || v_suffix;
    SELECT user_id INTO v_student_user_id FROM identity.app_user WHERE username = 'student_smoke_' || v_suffix;
    SELECT user_id INTO v_instructor_user_id FROM identity.app_user WHERE username = 'instructor_smoke_' || v_suffix;
    SELECT user_id INTO v_disabled_admin_user_id FROM identity.app_user WHERE username = 'disabled_admin_smoke_' || v_suffix;

    INSERT INTO identity.user_role (user_id, role_id, assigned_at, is_active)
    VALUES
        (v_admin_user_id, v_admin_role_id, now(), true),
        (v_student_user_id, v_student_role_id, now(), true),
        (v_instructor_user_id, v_instructor_role_id, now(), true),
        (v_disabled_admin_user_id, v_admin_role_id, now(), true);

    SELECT identity.has_permission(v_admin_user_id, 'test.future_feature') INTO v_result;
    IF v_result IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'ADMIN should automatically have new active permission via super-admin role';
    END IF;

    SELECT identity.has_permission(v_student_user_id, 'test.future_feature') INTO v_result;
    IF v_result IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'STUDENT must not automatically inherit arbitrary new permission';
    END IF;

    SELECT identity.has_permission(v_admin_user_id, 'test.non_existing_permission') INTO v_result;
    IF v_result IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Unknown permission code must return false';
    END IF;

    SELECT identity.has_permission(v_admin_user_id, 'test.inactive_feature') INTO v_result;
    IF v_result IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Inactive permission must return false even for super-admin';
    END IF;

    SELECT identity.has_permission(v_disabled_admin_user_id, 'test.future_feature') INTO v_result;
    IF v_result IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Inactive/disabled user must not pass permission checks';
    END IF;

    SELECT identity.has_permission(v_student_user_id, 'exam.submit') INTO v_result;
    IF v_result IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Regression: STUDENT must keep exam.submit';
    END IF;

    SELECT identity.has_permission(v_student_user_id, 'user.manage') INTO v_result;
    IF v_result IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Regression: STUDENT must not have user.manage';
    END IF;

    SELECT identity.has_permission(v_student_user_id, 'system.configure') INTO v_result;
    IF v_result IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Regression: STUDENT must not have system.configure';
    END IF;

    SELECT identity.has_permission(v_student_user_id, 'grading.grade') INTO v_result;
    IF v_result IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Regression: STUDENT must not have grading.grade';
    END IF;

    SELECT identity.has_permission(v_student_user_id, 'question.create') INTO v_result;
    IF v_result IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Regression: STUDENT must not have question.create';
    END IF;

    SELECT identity.has_permission(v_instructor_user_id, 'question.create') INTO v_result;
    IF v_result IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Regression: INSTRUCTOR must keep question.create';
    END IF;

    SELECT identity.has_permission(v_instructor_user_id, 'question.update') INTO v_result;
    IF v_result IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Regression: INSTRUCTOR must keep question.update';
    END IF;

    SELECT identity.has_permission(v_instructor_user_id, 'grading.grade') INTO v_result;
    IF v_result IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Regression: INSTRUCTOR must keep grading.grade';
    END IF;

    SELECT identity.has_permission(v_instructor_user_id, 'user.manage') INTO v_result;
    IF v_result IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Regression: INSTRUCTOR must not have user.manage';
    END IF;

    SELECT identity.has_permission(v_instructor_user_id, 'system.configure') INTO v_result;
    IF v_result IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Regression: INSTRUCTOR must not have system.configure';
    END IF;

    RAISE NOTICE 'PASS: has_permission super-admin semantics and regressions are correct.';
END
$$;

ROLLBACK;