-- Seed baseline function-level RBAC permission catalog and role-permission mappings.
-- Idempotent by permission_code and (role_id, permission_id) unique constraints.

INSERT INTO identity.permission (
    permission_code,
    module_code,
    action_code,
    permission_name,
    description,
    is_sensitive,
    is_active
)
VALUES
    ('user.view', 'user', 'view', 'View Users', 'View user directory and user profile metadata.', false, true),
    ('user.manage', 'user', 'manage', 'Manage Users', 'Create, update, disable, and administer user accounts.', true, true),
    ('role.view', 'role', 'view', 'View Roles', 'View role definitions and role assignments.', false, true),
    ('role.manage', 'role', 'manage', 'Manage Roles', 'Create or update role definitions and role assignments.', true, true),
    ('permission.view', 'permission', 'view', 'View Permissions', 'View permission catalog and permission metadata.', false, true),
    ('permission.manage', 'permission', 'manage', 'Manage Permissions', 'Create or update permission catalog entries.', true, true),

    ('academic.view', 'academic', 'view', 'View Academic Data', 'View academic structures such as departments and programs.', false, true),
    ('academic.manage', 'academic', 'manage', 'Manage Academic Data', 'Manage academic structures and administrative academic records.', true, true),
    ('class.view', 'class', 'view', 'View Classes', 'View class sections and class rosters.', false, true),
    ('class.manage', 'class', 'manage', 'Manage Classes', 'Create and manage class sections and instructional assignments.', true, true),

    ('exam.view', 'exam', 'view', 'View Exams', 'View exam definitions and availability.', false, true),
    ('exam.create', 'exam', 'create', 'Create Exams', 'Create new exams and exam structures.', true, true),
    ('exam.update', 'exam', 'update', 'Update Exams', 'Update existing exams and exam settings.', true, true),
    ('exam.assign', 'exam', 'assign', 'Assign Exams', 'Assign exams to classes, sessions, or students.', true, true),
    ('question.view', 'question', 'view', 'View Questions', 'View exam question bank and question metadata.', false, true),
    ('question.create', 'question', 'create', 'Create Questions', 'Create question bank items.', true, true),
    ('question.update', 'question', 'update', 'Update Questions', 'Update question bank items.', true, true),
    ('question.delete', 'question', 'delete', 'Delete Questions', 'Delete question bank items.', true, true),

    ('exam.launch', 'exam', 'launch', 'Launch Exam Session', 'Start assigned exam session as an exam participant.', false, true),
    ('exam.submit', 'exam', 'submit', 'Submit Exam', 'Submit exam responses for grading workflow.', false, true),
    ('proctor.view', 'proctor', 'view', 'View Proctor Operations', 'View exam proctoring operations and signals.', false, true),
    ('proctor.manage', 'proctor', 'manage', 'Manage Proctor Operations', 'Manage proctoring controls and interventions.', true, true),

    ('submission.view_own', 'submission', 'view_own', 'View Own Submissions', 'View only submissions owned by current student.', false, true),
    ('submission.view_class', 'submission', 'view_class', 'View Class Submissions', 'View submissions within assigned teaching/proctor scope.', true, true),
    ('submission.view_all', 'submission', 'view_all', 'View All Submissions', 'View all submissions across system scope.', true, true),
    ('grading.view', 'grading', 'view', 'View Grading Data', 'View grading jobs, grading results, and scoring state.', false, true),
    ('grading.grade', 'grading', 'grade', 'Grade Submissions', 'Execute grading actions and score generation.', true, true),
    ('grading.override', 'grading', 'override', 'Override Grades', 'Apply grading overrides and adjustment authority.', true, true),

    ('report.view_own', 'report', 'view_own', 'View Own Reports', 'View personal reports and own result summaries.', false, true),
    ('report.view_class', 'report', 'view_class', 'View Class Reports', 'View class-level reports and aggregate results.', false, true),
    ('report.view_system', 'report', 'view_system', 'View System Reports', 'View institution-wide and system-level reporting.', true, true),
    ('system.configure', 'system', 'configure', 'Configure System', 'Manage system configuration and privileged operational settings.', true, true)
ON CONFLICT (permission_code)
DO UPDATE
SET
    module_code = EXCLUDED.module_code,
    action_code = EXCLUDED.action_code,
    permission_name = EXCLUDED.permission_name,
    description = EXCLUDED.description,
    is_sensitive = EXCLUDED.is_sensitive,
    is_active = EXCLUDED.is_active,
    updated_at = now();

DO
$$
DECLARE
    missing_roles text;
BEGIN
    SELECT string_agg(expected_role, ', ' ORDER BY expected_role)
    INTO missing_roles
    FROM (
        SELECT unnest(
            ARRAY['STUDENT', 'INSTRUCTOR', 'ADMIN', 'ACADEMIC_OFFICER', 'PROCTOR', 'GRADER']
        ) AS expected_role
    ) src
    WHERE NOT EXISTS (
        SELECT 1
        FROM identity.role r
        WHERE r.role_code = src.expected_role
    );

    IF missing_roles IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required roles for RBAC permission seed: %', missing_roles;
    END IF;
END
$$;

WITH role_permission_seed(role_code, permission_code) AS (
    VALUES
        -- STUDENT
        ('STUDENT', 'class.view'),
        ('STUDENT', 'exam.view'),
        ('STUDENT', 'exam.launch'),
        ('STUDENT', 'exam.submit'),
        ('STUDENT', 'submission.view_own'),
        ('STUDENT', 'report.view_own'),

        -- INSTRUCTOR
        ('INSTRUCTOR', 'academic.view'),
        ('INSTRUCTOR', 'class.view'),
        ('INSTRUCTOR', 'class.manage'),
        ('INSTRUCTOR', 'exam.view'),
        ('INSTRUCTOR', 'exam.create'),
        ('INSTRUCTOR', 'exam.update'),
        ('INSTRUCTOR', 'exam.assign'),
        ('INSTRUCTOR', 'question.view'),
        ('INSTRUCTOR', 'question.create'),
        ('INSTRUCTOR', 'question.update'),
        ('INSTRUCTOR', 'submission.view_class'),
        ('INSTRUCTOR', 'grading.view'),
        ('INSTRUCTOR', 'grading.grade'),
        ('INSTRUCTOR', 'report.view_class'),

        -- ACADEMIC_OFFICER
        ('ACADEMIC_OFFICER', 'user.view'),
        ('ACADEMIC_OFFICER', 'academic.view'),
        ('ACADEMIC_OFFICER', 'academic.manage'),
        ('ACADEMIC_OFFICER', 'class.view'),
        ('ACADEMIC_OFFICER', 'class.manage'),
        ('ACADEMIC_OFFICER', 'exam.view'),
        ('ACADEMIC_OFFICER', 'exam.assign'),
        ('ACADEMIC_OFFICER', 'report.view_system'),

        -- PROCTOR
        ('PROCTOR', 'class.view'),
        ('PROCTOR', 'exam.view'),
        ('PROCTOR', 'proctor.view'),
        ('PROCTOR', 'proctor.manage'),
        ('PROCTOR', 'report.view_class'),

        -- GRADER
        ('GRADER', 'exam.view'),
        ('GRADER', 'question.view'),
        ('GRADER', 'submission.view_class'),
        ('GRADER', 'grading.view'),
        ('GRADER', 'grading.grade'),
        ('GRADER', 'report.view_class')
)
INSERT INTO identity.role_permission (
    role_id,
    permission_id,
    granted_by,
    is_active
)
SELECT
    r.role_id,
    p.permission_id,
    NULL,
    true
FROM role_permission_seed s
JOIN identity.role r
    ON r.role_code = s.role_code
JOIN identity.permission p
    ON p.permission_code = s.permission_code
ON CONFLICT (role_id, permission_id)
DO UPDATE
SET
    is_active = EXCLUDED.is_active;

INSERT INTO identity.role_permission (
    role_id,
    permission_id,
    granted_by,
    is_active
)
SELECT
    ar.role_id,
    p.permission_id,
    NULL,
    true
FROM identity.role ar
CROSS JOIN identity.permission p
WHERE ar.role_code = 'ADMIN'
  AND p.is_active = true
ON CONFLICT (role_id, permission_id)
DO UPDATE
SET
    is_active = EXCLUDED.is_active;
