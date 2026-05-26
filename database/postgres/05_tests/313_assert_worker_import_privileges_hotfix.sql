-- Worker import privilege smoke test (hotfix verification).
-- Scope: verifies worker-role privileges only.
-- Note: login membership still must be configured operationally:
--       GRANT exam_sys_worker TO exam_sys_worker_user;

DO
$$
BEGIN
    -- 1) Role existence
    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'exam_sys_worker'
    ) THEN
        RAISE EXCEPTION 'Missing role exam_sys_worker. Apply worker import privilege hotfix migration first.';
    END IF;
    -- 2) importing.* privileges required by worker import runtime
    IF NOT has_schema_privilege('exam_sys_worker', 'importing', 'USAGE') THEN
        RAISE EXCEPTION 'exam_sys_worker must have USAGE on schema importing';
    END IF;

    IF to_regclass('importing.import_row_error') IS NULL THEN
        RAISE EXCEPTION 'Table importing.import_row_error does not exist';
    END IF;
    IF NOT has_table_privilege('exam_sys_worker', 'importing.import_row_error', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_worker must have SELECT on importing.import_row_error';
    END IF;
    IF NOT has_table_privilege('exam_sys_worker', 'importing.import_row_error', 'INSERT') THEN
        RAISE EXCEPTION 'exam_sys_worker must have INSERT on importing.import_row_error';
    END IF;
    IF NOT has_table_privilege('exam_sys_worker', 'importing.import_row_error', 'UPDATE') THEN
        RAISE EXCEPTION 'exam_sys_worker must have UPDATE on importing.import_row_error';
    END IF;
    IF NOT has_table_privilege('exam_sys_worker', 'importing.import_row_error', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_worker must have DELETE on importing.import_row_error';
    END IF;

    IF to_regclass('importing.import_job') IS NULL THEN
        RAISE EXCEPTION 'Table importing.import_job does not exist';
    END IF;
    IF NOT has_table_privilege('exam_sys_worker', 'importing.import_job', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_worker must have SELECT on importing.import_job';
    END IF;
    IF NOT has_table_privilege('exam_sys_worker', 'importing.import_job', 'UPDATE') THEN
        RAISE EXCEPTION 'exam_sys_worker must have UPDATE on importing.import_job';
    END IF;

    IF to_regclass('importing.import_row_staging') IS NULL THEN
        RAISE EXCEPTION 'Table importing.import_row_staging does not exist';
    END IF;
    IF NOT has_table_privilege('exam_sys_worker', 'importing.import_row_staging', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_worker must have SELECT on importing.import_row_staging';
    END IF;
    IF NOT has_table_privilege('exam_sys_worker', 'importing.import_row_staging', 'UPDATE') THEN
        RAISE EXCEPTION 'exam_sys_worker must have UPDATE on importing.import_row_staging';
    END IF;

    -- 3) identity.* privileges for instructor import path
    IF NOT has_schema_privilege('exam_sys_worker', 'identity', 'USAGE') THEN
        RAISE EXCEPTION 'exam_sys_worker must have USAGE on schema identity';
    END IF;

    IF to_regclass('identity.person') IS NULL THEN
        RAISE EXCEPTION 'Table identity.person does not exist';
    END IF;
    IF NOT has_table_privilege('exam_sys_worker', 'identity.person', 'SELECT,INSERT,UPDATE') THEN
        RAISE EXCEPTION 'exam_sys_worker must have SELECT, INSERT, UPDATE on identity.person';
    END IF;

    IF to_regclass('identity.instructor_profile') IS NULL THEN
        RAISE EXCEPTION 'Table identity.instructor_profile does not exist';
    END IF;
    IF NOT has_table_privilege('exam_sys_worker', 'identity.instructor_profile', 'SELECT,INSERT,UPDATE') THEN
        RAISE EXCEPTION 'exam_sys_worker must have SELECT, INSERT, UPDATE on identity.instructor_profile';
    END IF;

    IF to_regclass('identity.app_user') IS NULL THEN
        RAISE EXCEPTION 'Table identity.app_user does not exist';
    END IF;
    IF NOT has_table_privilege('exam_sys_worker', 'identity.app_user', 'SELECT,INSERT,UPDATE') THEN
        RAISE EXCEPTION 'exam_sys_worker must have SELECT, INSERT, UPDATE on identity.app_user';
    END IF;

    IF to_regclass('identity.user_role') IS NULL THEN
        RAISE EXCEPTION 'Table identity.user_role does not exist';
    END IF;
    IF NOT has_table_privilege('exam_sys_worker', 'identity.user_role', 'SELECT,INSERT,UPDATE') THEN
        RAISE EXCEPTION 'exam_sys_worker must have SELECT, INSERT, UPDATE on identity.user_role';
    END IF;

    IF to_regclass('identity.role') IS NULL THEN
        RAISE EXCEPTION 'Table identity.role does not exist';
    END IF;
    IF NOT has_table_privilege('exam_sys_worker', 'identity.role', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_worker must have SELECT on identity.role';
    END IF;

    -- optional identity tables (only check if present)
    IF to_regclass('identity.contact_point') IS NOT NULL
       AND NOT has_table_privilege('exam_sys_worker', 'identity.contact_point', 'SELECT,INSERT,UPDATE') THEN
        RAISE EXCEPTION 'exam_sys_worker must have SELECT, INSERT, UPDATE on optional table identity.contact_point';
    END IF;

    IF to_regclass('identity.address') IS NOT NULL
       AND NOT has_table_privilege('exam_sys_worker', 'identity.address', 'SELECT,INSERT,UPDATE') THEN
        RAISE EXCEPTION 'exam_sys_worker must have SELECT, INSERT, UPDATE on optional table identity.address';
    END IF;

    IF to_regclass('identity.student_profile') IS NOT NULL
       AND NOT has_table_privilege('exam_sys_worker', 'identity.student_profile', 'SELECT,INSERT,UPDATE') THEN
        RAISE EXCEPTION 'exam_sys_worker must have SELECT, INSERT, UPDATE on optional table identity.student_profile';
    END IF;

    -- 4) academic reference privileges
    IF NOT has_schema_privilege('exam_sys_worker', 'academic', 'USAGE') THEN
        RAISE EXCEPTION 'exam_sys_worker must have USAGE on schema academic';
    END IF;

    IF to_regclass('academic.department') IS NULL THEN
        RAISE EXCEPTION 'Table academic.department does not exist';
    END IF;
    IF NOT has_table_privilege('exam_sys_worker', 'academic.department', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_worker must have SELECT on academic.department';
    END IF;

    IF to_regclass('academic.program') IS NOT NULL
       AND NOT has_table_privilege('exam_sys_worker', 'academic.program', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_worker must have SELECT on academic.program';
    END IF;

    IF to_regclass('academic.course') IS NOT NULL
       AND NOT has_table_privilege('exam_sys_worker', 'academic.course', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_worker must have SELECT on academic.course';
    END IF;

    -- 5) guard: API role must not be broadened with worker-only privileges
    IF to_regclass('importing.import_row_error') IS NOT NULL
       AND has_table_privilege('exam_sys_app', 'importing.import_row_error', 'DELETE') THEN
        RAISE EXCEPTION
            'Guard failed: exam_sys_app has DELETE on importing.import_row_error. Legacy/manual broad grant should be repaired.';
    END IF;

    RAISE NOTICE 'PASS: worker import privilege hotfix checks passed.';
END
$$;
