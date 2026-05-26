-- Split runtime DB role privileges between API and worker in LAN/runtime setup.
-- Keeps API role minimal while enabling worker import processing privileges.

DO
$$
DECLARE
    target_db text := current_database();
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_worker') THEN
        CREATE ROLE exam_sys_worker NOLOGIN;
    END IF;

    EXECUTE format('GRANT CONNECT ON DATABASE %I TO exam_sys_worker', target_db);
END
$$;

DO
$$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_worker') THEN
        GRANT USAGE ON SCHEMA importing TO exam_sys_worker;
        GRANT USAGE ON SCHEMA ops TO exam_sys_worker;

        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA importing TO exam_sys_worker;
        GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA ops TO exam_sys_worker;

        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA importing TO exam_sys_worker;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ops TO exam_sys_worker;

        ALTER DEFAULT PRIVILEGES FOR ROLE exam_sys_owner IN SCHEMA importing
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO exam_sys_worker;
        ALTER DEFAULT PRIVILEGES FOR ROLE exam_sys_owner IN SCHEMA importing
            GRANT USAGE, SELECT ON SEQUENCES TO exam_sys_worker;
    END IF;
END
$$;

DO
$$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_app') THEN
        REVOKE DELETE ON importing.import_row_error FROM exam_sys_app;
    END IF;
END
$$;

