-- Verifies RBAC grants and least-privilege posture.

DO
$$
BEGIN
    IF NOT has_table_privilege('exam_sys_app', 'identity.permission', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_app must have SELECT on identity.permission';
    END IF;
    IF NOT has_table_privilege('exam_sys_app', 'identity.permission', 'INSERT') THEN
        RAISE EXCEPTION 'exam_sys_app must have INSERT on identity.permission';
    END IF;
    IF NOT has_table_privilege('exam_sys_app', 'identity.permission', 'UPDATE') THEN
        RAISE EXCEPTION 'exam_sys_app must have UPDATE on identity.permission';
    END IF;

    IF NOT has_table_privilege('exam_sys_app', 'identity.role_permission', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_app must have SELECT on identity.role_permission';
    END IF;
    IF NOT has_table_privilege('exam_sys_app', 'identity.role_permission', 'INSERT') THEN
        RAISE EXCEPTION 'exam_sys_app must have INSERT on identity.role_permission';
    END IF;
    IF NOT has_table_privilege('exam_sys_app', 'identity.role_permission', 'UPDATE') THEN
        RAISE EXCEPTION 'exam_sys_app must have UPDATE on identity.role_permission';
    END IF;

    IF has_table_privilege('exam_sys_app', 'identity.permission', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on identity.permission';
    END IF;

    IF has_table_privilege('exam_sys_app', 'identity.role_permission', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on identity.role_permission';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'identity.v_role_permission_matrix', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on identity.v_role_permission_matrix';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'identity.v_user_effective_permission', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on identity.v_user_effective_permission';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'identity.permission', 'INSERT')
       OR has_table_privilege('exam_sys_readonly', 'identity.permission', 'UPDATE')
       OR has_table_privilege('exam_sys_readonly', 'identity.permission', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have write privileges on identity.permission';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'identity.role_permission', 'INSERT')
       OR has_table_privilege('exam_sys_readonly', 'identity.role_permission', 'UPDATE')
       OR has_table_privilege('exam_sys_readonly', 'identity.role_permission', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have write privileges on identity.role_permission';
    END IF;

    RAISE NOTICE 'PASS: RBAC grants and privileges are correct.';
END
$$;
