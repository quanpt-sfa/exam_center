-- Verifies required RBAC permission codes are seeded.

DO
$$
DECLARE
    v_missing_permissions text;
BEGIN
    SELECT string_agg(required_code, ', ' ORDER BY required_code)
    INTO v_missing_permissions
    FROM (
        SELECT unnest(
            ARRAY[
                'user.view',
                'user.manage',
                'role.view',
                'role.manage',
                'permission.view',
                'permission.manage',
                'academic.view',
                'academic.manage',
                'class.view',
                'class.manage',
                'exam.view',
                'exam.create',
                'exam.update',
                'exam.assign',
                'question.view',
                'question.create',
                'question.update',
                'question.delete',
                'exam.launch',
                'exam.submit',
                'proctor.view',
                'proctor.manage',
                'submission.view_own',
                'submission.view_class',
                'submission.view_all',
                'grading.view',
                'grading.grade',
                'grading.override',
                'report.view_own',
                'report.view_class',
                'report.view_system',
                'system.configure'
            ]
        ) AS required_code
    ) src
    WHERE NOT EXISTS (
        SELECT 1
        FROM identity.permission p
        WHERE p.permission_code = src.required_code
    );

    IF v_missing_permissions IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required RBAC permission_code values: %', v_missing_permissions;
    END IF;

    RAISE NOTICE 'PASS: RBAC permission seed values exist.';
END
$$;
