-- Verifies RBAC helper functions on a transactional insert graph.

BEGIN;

DO
$$
DECLARE
    suffix text := 'SMOKE_RBAC_FN_' || txid_current()::text;

    v_person_id bigint;
    v_user_id bigint;
    v_student_role_id bigint;

    v_has_exam_submit boolean;
    v_has_user_manage boolean;
BEGIN
    SELECT role_id
    INTO v_student_role_id
    FROM identity.role
    WHERE role_code = 'STUDENT'
    LIMIT 1;

    IF v_student_role_id IS NULL THEN
        RAISE EXCEPTION 'Required role STUDENT is missing for transactional RBAC function test';
    END IF;

    INSERT INTO identity.person (
        full_name,
        person_status
    )
    VALUES (
        suffix || ' Person',
        'ACTIVE'
    )
    RETURNING person_id INTO v_person_id;

    INSERT INTO identity.app_user (
        person_id,
        username,
        email_login,
        password_hash,
        user_status
    )
    VALUES (
        v_person_id,
        lower(suffix) || '_user',
        lower(suffix) || '@local.test',
        'hash_rbac_fn_smoke',
        'ACTIVE'
    )
    RETURNING user_id INTO v_user_id;

    INSERT INTO identity.user_role (
        user_id,
        role_id,
        assigned_at,
        assigned_by,
        is_active
    )
    VALUES (
        v_user_id,
        v_student_role_id,
        now(),
        NULL,
        true
    );

    SELECT identity.has_permission(v_user_id, 'exam.submit')
    INTO v_has_exam_submit;

    IF v_has_exam_submit IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Expected has_permission(user_id, exam.submit) = true for STUDENT role';
    END IF;

    SELECT identity.has_permission(v_user_id, 'user.manage')
    INTO v_has_user_manage;

    IF v_has_user_manage IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Expected has_permission(user_id, user.manage) = false for STUDENT role';
    END IF;

    IF identity.has_any_permission(v_user_id, ARRAY['user.manage', 'exam.submit']::varchar[]) IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Expected has_any_permission to return true for mixed list including exam.submit';
    END IF;

    RAISE NOTICE 'PASS: RBAC function transactional insert graph assertions passed.';
END
$$;

ROLLBACK;
