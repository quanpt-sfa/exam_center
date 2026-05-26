-- Hotfix complement for 0114_split_api_worker_runtime_db_privileges.sql.
-- 0114 focuses on importing/ops job infrastructure privileges.
-- This migration grants worker access to master-data target/reference schemas/tables
-- needed by instructor/student import commit paths.
--
-- Boundary rule:
-- - grant only to exam_sys_worker
-- - do not broaden exam_sys_app with worker-only privileges
-- - do not create LOGIN users or store passwords in migrations

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'exam_sys_worker'
    ) THEN
        CREATE ROLE exam_sys_worker NOLOGIN;
    END IF;
END
$$;

-- identity target access for person/instructor/account/role mapping persistence.
GRANT USAGE ON SCHEMA identity TO exam_sys_worker;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA identity TO exam_sys_worker;

DO
$$
BEGIN
    IF to_regclass('identity.person') IS NOT NULL THEN
        GRANT SELECT, INSERT, UPDATE ON TABLE identity.person TO exam_sys_worker;
    END IF;

    IF to_regclass('identity.instructor_profile') IS NOT NULL THEN
        GRANT SELECT, INSERT, UPDATE ON TABLE identity.instructor_profile TO exam_sys_worker;
    END IF;

    IF to_regclass('identity.student_profile') IS NOT NULL THEN
        GRANT SELECT, INSERT, UPDATE ON TABLE identity.student_profile TO exam_sys_worker;
    END IF;

    IF to_regclass('identity.contact_point') IS NOT NULL THEN
        GRANT SELECT, INSERT, UPDATE ON TABLE identity.contact_point TO exam_sys_worker;
    END IF;

    IF to_regclass('identity.address') IS NOT NULL THEN
        GRANT SELECT, INSERT, UPDATE ON TABLE identity.address TO exam_sys_worker;
    END IF;

    IF to_regclass('identity.app_user') IS NOT NULL THEN
        GRANT SELECT, INSERT, UPDATE ON TABLE identity.app_user TO exam_sys_worker;
    END IF;

    IF to_regclass('identity.user_role') IS NOT NULL THEN
        GRANT SELECT, INSERT, UPDATE ON TABLE identity.user_role TO exam_sys_worker;
    END IF;

    IF to_regclass('identity.role') IS NOT NULL THEN
        GRANT SELECT ON TABLE identity.role TO exam_sys_worker;
    END IF;
END
$$;

-- academic reference/target access for import validation and course import targets.
GRANT USAGE ON SCHEMA academic TO exam_sys_worker;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA academic TO exam_sys_worker;

DO
$$
BEGIN
    IF to_regclass('academic.department') IS NOT NULL THEN
        GRANT SELECT ON TABLE academic.department TO exam_sys_worker;
    END IF;

    IF to_regclass('academic.program') IS NOT NULL THEN
        GRANT SELECT ON TABLE academic.program TO exam_sys_worker;
    END IF;

    IF to_regclass('academic.course') IS NOT NULL THEN
        -- Current import commit handlers write course rows when import_type = COURSES.
        GRANT SELECT, INSERT, UPDATE ON TABLE academic.course TO exam_sys_worker;
    END IF;
END
$$;

