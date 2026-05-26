-- Hotfix: grant master-data import runtime privileges to exam_sys_worker.
-- Boundary rule: do not broaden exam_sys_app to satisfy worker-only operations.
-- LOGIN users and passwords are intentionally not created in migrations.

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_worker'
    ) THEN
        -- Group role for background worker runtime only (NOLOGIN).
        CREATE ROLE exam_sys_worker NOLOGIN;
    END IF;
END
$$;

DO
$$
BEGIN
    EXECUTE format(
        'GRANT CONNECT ON DATABASE %I TO exam_sys_worker',
        current_database()
    );
END
$$;

-- Worker import lifecycle on importing.*:
-- DELETE on importing.import_row_error is required for worker row-error cleanup/re-validation loops.
GRANT USAGE ON SCHEMA importing TO exam_sys_worker;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA importing TO exam_sys_worker;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA importing TO exam_sys_worker;

DO
$$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_owner') THEN
        ALTER DEFAULT PRIVILEGES FOR ROLE exam_sys_owner IN SCHEMA importing
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO exam_sys_worker;
        ALTER DEFAULT PRIVILEGES FOR ROLE exam_sys_owner IN SCHEMA importing
            GRANT USAGE, SELECT ON SEQUENCES TO exam_sys_worker;
    END IF;
END
$$;

-- Instructor import and account provisioning need identity schema usage and table-level writes.
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

    IF to_regclass('identity.student_profile') IS NOT NULL THEN
        GRANT SELECT, INSERT, UPDATE ON TABLE identity.student_profile TO exam_sys_worker;
    END IF;

    IF to_regclass('identity.role') IS NOT NULL THEN
        GRANT SELECT ON TABLE identity.role TO exam_sys_worker;
    END IF;
END
$$;

-- Import handlers read academic reference data and may write academic.course for course imports.
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
        GRANT SELECT, INSERT, UPDATE ON TABLE academic.course TO exam_sys_worker;
    END IF;
END
$$;

