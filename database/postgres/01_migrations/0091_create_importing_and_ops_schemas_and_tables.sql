-- Phase import foundation: importing/ops schemas and controlled staging/audit tables.

CREATE SCHEMA IF NOT EXISTS importing;
CREATE SCHEMA IF NOT EXISTS ops;

COMMENT ON SCHEMA importing IS 'Import staging and validation schema for controlled Excel/CSV ingestion.';
COMMENT ON SCHEMA ops IS 'Operational command and audit schema for safe CLI/API operations.';

DO
$$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_owner') THEN
        ALTER SCHEMA importing OWNER TO exam_sys_owner;
        ALTER SCHEMA ops OWNER TO exam_sys_owner;
        GRANT CREATE ON SCHEMA importing TO exam_sys_owner;
        GRANT CREATE ON SCHEMA ops TO exam_sys_owner;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_app') THEN
        GRANT USAGE ON SCHEMA importing TO exam_sys_app;
        GRANT USAGE ON SCHEMA ops TO exam_sys_app;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_readonly') THEN
        GRANT USAGE ON SCHEMA importing TO exam_sys_readonly;
        GRANT USAGE ON SCHEMA ops TO exam_sys_readonly;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS importing.import_template (
    import_template_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    template_code varchar(100) NOT NULL,
    template_name varchar(255) NOT NULL,
    schema_version varchar(50) NOT NULL,
    entity_code varchar(100) NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_importing_import_template_template_code UNIQUE (template_code)
);

CREATE TABLE IF NOT EXISTS ops.agent_command (
    agent_command_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    command_code varchar(100) NOT NULL,
    description text NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_ops_agent_command_command_code UNIQUE (command_code)
);

CREATE TABLE IF NOT EXISTS ops.agent_permission_scope (
    agent_permission_scope_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_code varchar(100) NOT NULL,
    description text NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_ops_agent_permission_scope_scope_code UNIQUE (scope_code)
);

CREATE TABLE IF NOT EXISTS ops.agent_command_run (
    agent_command_run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    agent_command_id bigint NULL,
    actor_user_id bigint NULL,
    actor_agent varchar(255) NULL,
    command_text text NULL,
    run_status varchar(30) NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz NULL,
    output_json jsonb NULL,
    CONSTRAINT ck_ops_agent_command_run_status CHECK (
        run_status IN ('RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')
    ),
    CONSTRAINT fk_ops_agent_command_run_command FOREIGN KEY (agent_command_id)
        REFERENCES ops.agent_command(agent_command_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_ops_agent_command_run_actor_user FOREIGN KEY (actor_user_id)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS ops.agent_command_event (
    agent_command_event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    agent_command_run_id bigint NOT NULL,
    event_type varchar(100) NOT NULL,
    event_payload_json jsonb NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_ops_agent_command_event_run FOREIGN KEY (agent_command_run_id)
        REFERENCES ops.agent_command_run(agent_command_run_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS importing.import_job (
    import_job_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_template_id bigint NOT NULL,
    template_code varchar(100) NOT NULL,
    job_status varchar(30) NOT NULL,
    validation_status varchar(30) NOT NULL DEFAULT 'PENDING',
    commit_status varchar(30) NOT NULL DEFAULT 'NOT_COMMITTED',
    actor_user_id bigint NULL,
    actor_agent varchar(255) NULL,
    agent_command_run_id bigint NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT ck_importing_import_job_status CHECK (
        job_status IN ('CREATED', 'UPLOADED', 'PARSED', 'VALIDATED', 'COMMITTED', 'ROLLED_BACK', 'FAILED')
    ),
    CONSTRAINT ck_importing_import_job_validation_status CHECK (
        validation_status IN ('PENDING', 'PASSED', 'FAILED', 'PARTIAL')
    ),
    CONSTRAINT ck_importing_import_job_commit_status CHECK (
        commit_status IN ('NOT_COMMITTED', 'COMMITTED', 'ROLLED_BACK')
    ),
    CONSTRAINT fk_importing_import_job_template FOREIGN KEY (import_template_id)
        REFERENCES importing.import_template(import_template_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_importing_import_job_actor_user FOREIGN KEY (actor_user_id)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_importing_import_job_command_run FOREIGN KEY (agent_command_run_id)
        REFERENCES ops.agent_command_run(agent_command_run_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS importing.import_file (
    import_file_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_job_id bigint NOT NULL,
    original_filename varchar(500) NOT NULL,
    storage_ref text NULL,
    local_dev_path text NULL,
    file_size_bytes bigint NULL,
    uploaded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_importing_import_file_job FOREIGN KEY (import_job_id)
        REFERENCES importing.import_job(import_job_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS importing.import_sheet (
    import_sheet_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_file_id bigint NOT NULL,
    sheet_name varchar(255) NOT NULL,
    row_count integer NOT NULL DEFAULT 0,
    parsed_at timestamptz NULL,
    CONSTRAINT fk_importing_import_sheet_file FOREIGN KEY (import_file_id)
        REFERENCES importing.import_file(import_file_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS importing.import_column_mapping (
    import_column_mapping_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_job_id bigint NOT NULL,
    source_column varchar(255) NOT NULL,
    target_field varchar(255) NOT NULL,
    is_required boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_importing_import_column_mapping_job FOREIGN KEY (import_job_id)
        REFERENCES importing.import_job(import_job_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS importing.import_row_staging (
    import_row_staging_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_job_id bigint NOT NULL,
    import_sheet_id bigint NULL,
    row_number integer NOT NULL,
    raw_row_json jsonb NOT NULL,
    normalized_row_json jsonb NULL,
    validation_status varchar(30) NOT NULL DEFAULT 'PENDING',
    commit_status varchar(30) NOT NULL DEFAULT 'NOT_COMMITTED',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT ck_importing_import_row_staging_validation_status CHECK (
        validation_status IN ('PENDING', 'VALID', 'INVALID')
    ),
    CONSTRAINT ck_importing_import_row_staging_commit_status CHECK (
        commit_status IN ('NOT_COMMITTED', 'COMMITTED', 'FAILED')
    ),
    CONSTRAINT fk_importing_import_row_staging_job FOREIGN KEY (import_job_id)
        REFERENCES importing.import_job(import_job_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_importing_import_row_staging_sheet FOREIGN KEY (import_sheet_id)
        REFERENCES importing.import_sheet(import_sheet_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS importing.import_row_error (
    import_row_error_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_job_id bigint NOT NULL,
    import_row_staging_id bigint NOT NULL,
    error_code varchar(100) NOT NULL,
    error_message text NOT NULL,
    error_details_json jsonb NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_importing_import_row_error_job FOREIGN KEY (import_job_id)
        REFERENCES importing.import_job(import_job_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_importing_import_row_error_staging FOREIGN KEY (import_row_staging_id)
        REFERENCES importing.import_row_staging(import_row_staging_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS importing.import_commit (
    import_commit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_job_id bigint NOT NULL,
    commit_status varchar(30) NOT NULL,
    committed_at timestamptz NULL,
    committed_by bigint NULL,
    summary_json jsonb NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_importing_import_commit_status CHECK (
        commit_status IN ('PENDING', 'COMMITTED', 'FAILED', 'ROLLED_BACK')
    ),
    CONSTRAINT fk_importing_import_commit_job FOREIGN KEY (import_job_id)
        REFERENCES importing.import_job(import_job_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_importing_import_commit_user FOREIGN KEY (committed_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS importing.import_entity_link (
    import_entity_link_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_job_id bigint NOT NULL,
    import_row_staging_id bigint NOT NULL,
    entity_schema varchar(100) NOT NULL,
    entity_table varchar(100) NOT NULL,
    entity_pk varchar(255) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_importing_import_entity_link_job FOREIGN KEY (import_job_id)
        REFERENCES importing.import_job(import_job_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_importing_import_entity_link_staging FOREIGN KEY (import_row_staging_id)
        REFERENCES importing.import_row_staging(import_row_staging_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS importing.import_audit_event (
    import_audit_event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_job_id bigint NULL,
    event_type varchar(100) NOT NULL,
    event_payload_json jsonb NULL,
    actor_user_id bigint NULL,
    actor_agent varchar(255) NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_importing_import_audit_event_job FOREIGN KEY (import_job_id)
        REFERENCES importing.import_job(import_job_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_importing_import_audit_event_user FOREIGN KEY (actor_user_id)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_importing_import_job_template_code
    ON importing.import_job (template_code);
CREATE INDEX IF NOT EXISTS idx_importing_import_job_status
    ON importing.import_job (job_status);
CREATE INDEX IF NOT EXISTS idx_importing_import_row_staging_job
    ON importing.import_row_staging (import_job_id);
CREATE INDEX IF NOT EXISTS idx_importing_import_row_error_job
    ON importing.import_row_error (import_job_id);
CREATE INDEX IF NOT EXISTS idx_importing_import_audit_event_job
    ON importing.import_audit_event (import_job_id);
CREATE INDEX IF NOT EXISTS idx_ops_agent_command_run_status
    ON ops.agent_command_run (run_status);

DO
$$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_app') THEN
        GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA importing TO exam_sys_app;
        GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA ops TO exam_sys_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA importing TO exam_sys_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ops TO exam_sys_app;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_readonly') THEN
        GRANT SELECT ON importing.import_template TO exam_sys_readonly;
        GRANT SELECT ON importing.import_job TO exam_sys_readonly;
        GRANT SELECT ON importing.import_audit_event TO exam_sys_readonly;
        GRANT SELECT ON ops.agent_command TO exam_sys_readonly;
        GRANT SELECT ON ops.agent_command_run TO exam_sys_readonly;
        GRANT SELECT ON ops.agent_command_event TO exam_sys_readonly;
        GRANT SELECT ON ops.agent_permission_scope TO exam_sys_readonly;
    END IF;
END
$$;

REVOKE ALL ON SCHEMA importing FROM PUBLIC;
REVOKE ALL ON SCHEMA ops FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA importing FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA ops FROM PUBLIC;
