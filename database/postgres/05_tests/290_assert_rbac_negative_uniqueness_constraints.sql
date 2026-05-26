-- Verifies RBAC unique constraints reject duplicate writes.

BEGIN;

DO
$$
DECLARE
    duplicate_permission_code_conflict boolean := false;
    duplicate_role_permission_conflict boolean := false;

    v_student_role_id bigint;
    v_exam_submit_permission_id bigint;
BEGIN
    BEGIN
        INSERT INTO identity.permission (
            permission_code,
            module_code,
            action_code,
            permission_name,
            is_sensitive,
            is_active
        )
        VALUES (
            'user.view',
            'user',
            'view',
            'Duplicate User View',
            false,
            true
        );
    EXCEPTION
        WHEN unique_violation THEN
            duplicate_permission_code_conflict := true;
    END;

    IF NOT duplicate_permission_code_conflict THEN
        RAISE EXCEPTION 'Expected unique_violation for duplicate identity.permission.permission_code';
    END IF;

    SELECT role_id
    INTO v_student_role_id
    FROM identity.role
    WHERE role_code = 'STUDENT'
    LIMIT 1;

    SELECT permission_id
    INTO v_exam_submit_permission_id
    FROM identity.permission
    WHERE permission_code = 'exam.submit'
    LIMIT 1;

    IF v_student_role_id IS NULL OR v_exam_submit_permission_id IS NULL THEN
        RAISE EXCEPTION 'Missing STUDENT role or exam.submit permission for duplicate role_permission test';
    END IF;

    BEGIN
        INSERT INTO identity.role_permission (
            role_id,
            permission_id,
            granted_at,
            granted_by,
            is_active
        )
        VALUES (
            v_student_role_id,
            v_exam_submit_permission_id,
            now(),
            NULL,
            true
        );
    EXCEPTION
        WHEN unique_violation THEN
            duplicate_role_permission_conflict := true;
    END;

    IF NOT duplicate_role_permission_conflict THEN
        RAISE EXCEPTION 'Expected unique_violation for duplicate identity.role_permission(role_id, permission_id)';
    END IF;

    RAISE NOTICE 'PASS: RBAC negative uniqueness checks passed.';
END
$$;

ROLLBACK;
