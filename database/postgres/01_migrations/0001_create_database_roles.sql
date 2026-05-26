-- Phase 1 source: docs/phase_1_database_architecture.md
-- Creates technical database roles for ownership and runtime access.

DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_owner') THEN
        CREATE ROLE exam_sys_owner NOLOGIN;
    END IF;
END
$$;

DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_app') THEN
        CREATE ROLE exam_sys_app NOLOGIN;
    END IF;
END
$$;

DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_readonly') THEN
        CREATE ROLE exam_sys_readonly NOLOGIN;
    END IF;
END
$$;

COMMENT ON ROLE exam_sys_owner IS 'Owns PostgreSQL objects for exam_sys_dev (local development).';
COMMENT ON ROLE exam_sys_app IS 'Application runtime access role for exam_sys_dev (local development).';
COMMENT ON ROLE exam_sys_readonly IS 'Read-only access role for exam_sys_dev (local development).';

DO
$$
DECLARE
    target_db text := current_database();
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO exam_sys_owner', target_db);
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO exam_sys_app', target_db);
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO exam_sys_readonly', target_db);
END
$$;
