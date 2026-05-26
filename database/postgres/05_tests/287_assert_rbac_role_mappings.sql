-- Verifies required RBAC role-permission mappings.

DO
$$
DECLARE
    v_has_student_exam_submit boolean;
    v_has_student_submission_view_own boolean;
    v_has_student_user_manage boolean;
    v_has_student_grading_grade boolean;
    v_has_student_system_configure boolean;

    v_has_instructor_question_create boolean;
    v_has_instructor_grading_grade boolean;
    v_has_instructor_user_manage boolean;
    v_has_instructor_system_configure boolean;

    v_has_proctor_view boolean;
    v_has_proctor_manage boolean;
    v_has_grader_grade boolean;

    v_admin_active_permission_count integer;
    v_total_active_permission_count integer;
    v_admin_is_super_admin boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM identity.role_permission rp
        JOIN identity.role r ON r.role_id = rp.role_id
        JOIN identity.permission p ON p.permission_id = rp.permission_id
        WHERE r.role_code = 'STUDENT'
          AND p.permission_code = 'exam.submit'
          AND r.is_active = true
          AND rp.is_active = true
          AND p.is_active = true
    ) INTO v_has_student_exam_submit;

    SELECT EXISTS (
        SELECT 1
        FROM identity.role_permission rp
        JOIN identity.role r ON r.role_id = rp.role_id
        JOIN identity.permission p ON p.permission_id = rp.permission_id
        WHERE r.role_code = 'STUDENT'
          AND p.permission_code = 'submission.view_own'
          AND r.is_active = true
          AND rp.is_active = true
          AND p.is_active = true
    ) INTO v_has_student_submission_view_own;

    SELECT EXISTS (
        SELECT 1
        FROM identity.role_permission rp
        JOIN identity.role r ON r.role_id = rp.role_id
        JOIN identity.permission p ON p.permission_id = rp.permission_id
        WHERE r.role_code = 'STUDENT'
          AND p.permission_code = 'user.manage'
          AND r.is_active = true
          AND rp.is_active = true
          AND p.is_active = true
    ) INTO v_has_student_user_manage;

    SELECT EXISTS (
        SELECT 1
        FROM identity.role_permission rp
        JOIN identity.role r ON r.role_id = rp.role_id
        JOIN identity.permission p ON p.permission_id = rp.permission_id
        WHERE r.role_code = 'STUDENT'
          AND p.permission_code = 'grading.grade'
          AND r.is_active = true
          AND rp.is_active = true
          AND p.is_active = true
    ) INTO v_has_student_grading_grade;

    SELECT EXISTS (
        SELECT 1
        FROM identity.role_permission rp
        JOIN identity.role r ON r.role_id = rp.role_id
        JOIN identity.permission p ON p.permission_id = rp.permission_id
        WHERE r.role_code = 'STUDENT'
          AND p.permission_code = 'system.configure'
          AND r.is_active = true
          AND rp.is_active = true
          AND p.is_active = true
    ) INTO v_has_student_system_configure;

    SELECT EXISTS (
        SELECT 1
        FROM identity.role_permission rp
        JOIN identity.role r ON r.role_id = rp.role_id
        JOIN identity.permission p ON p.permission_id = rp.permission_id
        WHERE r.role_code = 'INSTRUCTOR'
          AND p.permission_code = 'question.create'
          AND r.is_active = true
          AND rp.is_active = true
          AND p.is_active = true
    ) INTO v_has_instructor_question_create;

    SELECT EXISTS (
        SELECT 1
        FROM identity.role_permission rp
        JOIN identity.role r ON r.role_id = rp.role_id
        JOIN identity.permission p ON p.permission_id = rp.permission_id
        WHERE r.role_code = 'INSTRUCTOR'
          AND p.permission_code = 'grading.grade'
          AND r.is_active = true
          AND rp.is_active = true
          AND p.is_active = true
    ) INTO v_has_instructor_grading_grade;

    SELECT EXISTS (
        SELECT 1
        FROM identity.role_permission rp
        JOIN identity.role r ON r.role_id = rp.role_id
        JOIN identity.permission p ON p.permission_id = rp.permission_id
        WHERE r.role_code = 'INSTRUCTOR'
          AND p.permission_code = 'user.manage'
          AND r.is_active = true
          AND rp.is_active = true
          AND p.is_active = true
    ) INTO v_has_instructor_user_manage;

    SELECT EXISTS (
        SELECT 1
        FROM identity.role_permission rp
        JOIN identity.role r ON r.role_id = rp.role_id
        JOIN identity.permission p ON p.permission_id = rp.permission_id
        WHERE r.role_code = 'INSTRUCTOR'
          AND p.permission_code = 'system.configure'
          AND r.is_active = true
          AND rp.is_active = true
          AND p.is_active = true
    ) INTO v_has_instructor_system_configure;

    SELECT EXISTS (
        SELECT 1
        FROM identity.role_permission rp
        JOIN identity.role r ON r.role_id = rp.role_id
        JOIN identity.permission p ON p.permission_id = rp.permission_id
        WHERE r.role_code = 'PROCTOR'
          AND p.permission_code = 'proctor.view'
          AND r.is_active = true
          AND rp.is_active = true
          AND p.is_active = true
    ) INTO v_has_proctor_view;

    SELECT EXISTS (
        SELECT 1
        FROM identity.role_permission rp
        JOIN identity.role r ON r.role_id = rp.role_id
        JOIN identity.permission p ON p.permission_id = rp.permission_id
        WHERE r.role_code = 'PROCTOR'
          AND p.permission_code = 'proctor.manage'
          AND r.is_active = true
          AND rp.is_active = true
          AND p.is_active = true
    ) INTO v_has_proctor_manage;

    SELECT EXISTS (
        SELECT 1
        FROM identity.role_permission rp
        JOIN identity.role r ON r.role_id = rp.role_id
        JOIN identity.permission p ON p.permission_id = rp.permission_id
        WHERE r.role_code = 'GRADER'
          AND p.permission_code = 'grading.grade'
          AND r.is_active = true
          AND rp.is_active = true
          AND p.is_active = true
    ) INTO v_has_grader_grade;

    SELECT count(*)
    INTO v_total_active_permission_count
    FROM identity.permission p
    WHERE p.is_active = true;

        SELECT count(DISTINCT m.permission_code)
    INTO v_admin_active_permission_count
        FROM identity.v_role_permission_matrix m
        WHERE m.role_code = 'ADMIN';

        SELECT COALESCE(bool_or(r.is_super_admin), false)
        INTO v_admin_is_super_admin
        FROM identity.role r
        WHERE r.role_code = 'ADMIN'
            AND r.is_active = true;

    IF NOT v_has_student_exam_submit THEN
        RAISE EXCEPTION 'STUDENT must have exam.submit';
    END IF;
    IF NOT v_has_student_submission_view_own THEN
        RAISE EXCEPTION 'STUDENT must have submission.view_own';
    END IF;
    IF v_has_student_user_manage THEN
        RAISE EXCEPTION 'STUDENT must not have user.manage';
    END IF;
    IF v_has_student_grading_grade THEN
        RAISE EXCEPTION 'STUDENT must not have grading.grade';
    END IF;
    IF v_has_student_system_configure THEN
        RAISE EXCEPTION 'STUDENT must not have system.configure';
    END IF;

    IF NOT v_has_instructor_question_create THEN
        RAISE EXCEPTION 'INSTRUCTOR must have question.create';
    END IF;
    IF NOT v_has_instructor_grading_grade THEN
        RAISE EXCEPTION 'INSTRUCTOR must have grading.grade';
    END IF;
    IF v_has_instructor_user_manage THEN
        RAISE EXCEPTION 'INSTRUCTOR must not have user.manage';
    END IF;
    IF v_has_instructor_system_configure THEN
        RAISE EXCEPTION 'INSTRUCTOR must not have system.configure';
    END IF;

    IF v_admin_active_permission_count <> v_total_active_permission_count THEN
        RAISE EXCEPTION 'ADMIN must have all active permissions. Admin=% Total=%',
            v_admin_active_permission_count,
            v_total_active_permission_count;
    END IF;

    IF v_admin_is_super_admin IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'ADMIN must be marked as is_super_admin=true';
    END IF;

    IF NOT v_has_proctor_view OR NOT v_has_proctor_manage THEN
        RAISE EXCEPTION 'PROCTOR must have proctor.view and proctor.manage';
    END IF;

    IF NOT v_has_grader_grade THEN
        RAISE EXCEPTION 'GRADER must have grading.grade';
    END IF;

    RAISE NOTICE 'PASS: RBAC role mappings are correct.';
END
$$;
