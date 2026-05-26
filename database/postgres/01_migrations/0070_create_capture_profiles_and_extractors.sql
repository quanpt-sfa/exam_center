-- Phase 4.7.2 source: docs/phase_4_7_assessment_modality_grading_profile_foundation.md
-- Creates capture profile and extractor registry foundation for post-seal capture configuration.

CREATE TABLE IF NOT EXISTS capture.capture_profile (
    capture_profile_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    profile_code varchar(100) NOT NULL,
    profile_name varchar(255) NOT NULL,
    source_type varchar(50) NOT NULL,
    source_location_mode varchar(50) NOT NULL,
    default_capture_timing varchar(50) NOT NULL,
    requires_agent boolean NOT NULL DEFAULT false,
    description text NULL,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_capture_capture_profile_profile_code UNIQUE (profile_code),
    CONSTRAINT ck_capture_capture_profile_source_type CHECK (
        source_type IN (
            'SQLSERVER_DATABASE',
            'POSTGRES_DATABASE',
            'MISA_DATABASE',
            'AMIS_API',
            'FILE_UPLOAD',
            'CUSTOM_API',
            'OTHER'
        )
    ),
    CONSTRAINT ck_capture_capture_profile_location_mode CHECK (
        source_location_mode IN (
            'SERVER_HOSTED',
            'STUDENT_DEVICE_LOCAL',
            'EXTERNAL_SAAS',
            'MANUAL_UPLOAD',
            'MIXED'
        )
    ),
    CONSTRAINT ck_capture_capture_profile_default_timing CHECK (
        default_capture_timing IN (
            'NONE',
            'AFTER_SEAL',
            'MANUAL_UPLOAD_AFTER_SEAL'
        )
    ),
    CONSTRAINT ck_capture_capture_profile_status CHECK (
        status IN ('DRAFT', 'ACTIVE', 'RETIRED', 'DISABLED')
    ),
    CONSTRAINT ck_capture_capture_profile_updated_at CHECK (
        updated_at IS NULL OR updated_at >= created_at
    )
);

CREATE TABLE IF NOT EXISTS capture.capture_extractor_query (
    capture_extractor_query_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capture_profile_id bigint NOT NULL,
    query_code varchar(100) NOT NULL,
    query_name varchar(255) NOT NULL,
    extractor_kind varchar(50) NOT NULL,
    query_text text NULL,
    output_dataset_name varchar(255) NOT NULL,
    is_required boolean NOT NULL DEFAULT true,
    execution_order integer NOT NULL DEFAULT 1,
    timeout_seconds integer NULL,
    normalizer_code varchar(100) NULL,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_capture_capture_extractor_query_profile_code UNIQUE (capture_profile_id, query_code),
    CONSTRAINT uq_capture_capture_extractor_query_profile_dataset UNIQUE (capture_profile_id, output_dataset_name),
    CONSTRAINT ck_capture_capture_extractor_query_kind CHECK (
        extractor_kind IN (
            'SQL_QUERY',
            'API_ENDPOINT',
            'SCRIPT_REF',
            'FILE_PATTERN',
            'MANUAL_CHECK',
            'OTHER'
        )
    ),
    CONSTRAINT ck_capture_capture_extractor_query_status CHECK (
        status IN ('DRAFT', 'ACTIVE', 'RETIRED', 'DISABLED')
    ),
    CONSTRAINT ck_capture_capture_extractor_query_execution_order CHECK (execution_order > 0),
    CONSTRAINT ck_capture_capture_extractor_query_timeout CHECK (
        timeout_seconds IS NULL OR timeout_seconds > 0
    ),
    CONSTRAINT ck_capture_capture_extractor_query_updated_at CHECK (
        updated_at IS NULL OR updated_at >= created_at
    ),
    CONSTRAINT fk_capture_capture_extractor_query_profile FOREIGN KEY (capture_profile_id)
        REFERENCES capture.capture_profile(capture_profile_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS capture.capture_profile_engine_link (
    capture_profile_engine_link_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capture_profile_id bigint NOT NULL,
    grading_engine_id bigint NOT NULL,
    link_role varchar(50) NOT NULL DEFAULT 'SUPPORTED',
    is_active boolean NOT NULL DEFAULT true,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_capture_capture_profile_engine_link UNIQUE (capture_profile_id, grading_engine_id, link_role),
    CONSTRAINT ck_capture_capture_profile_engine_link_role CHECK (
        link_role IN ('DEFAULT', 'SUPPORTED', 'FALLBACK')
    ),
    CONSTRAINT fk_capture_capture_profile_engine_link_profile FOREIGN KEY (capture_profile_id)
        REFERENCES capture.capture_profile(capture_profile_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_capture_capture_profile_engine_link_engine FOREIGN KEY (grading_engine_id)
        REFERENCES grading.grading_engine(grading_engine_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_capture_capture_extractor_query_profile_id
    ON capture.capture_extractor_query (capture_profile_id);

CREATE INDEX IF NOT EXISTS idx_capture_capture_profile_engine_link_profile_id
    ON capture.capture_profile_engine_link (capture_profile_id);

CREATE INDEX IF NOT EXISTS idx_capture_capture_profile_engine_link_engine_id
    ON capture.capture_profile_engine_link (grading_engine_id);

CREATE INDEX IF NOT EXISTS idx_capture_capture_profile_source_type
    ON capture.capture_profile (source_type);

CREATE INDEX IF NOT EXISTS idx_capture_capture_profile_source_location_mode
    ON capture.capture_profile (source_location_mode);

CREATE INDEX IF NOT EXISTS idx_capture_capture_profile_status
    ON capture.capture_profile (status);

INSERT INTO capture.capture_profile (
    profile_code,
    profile_name,
    source_type,
    source_location_mode,
    default_capture_timing,
    requires_agent,
    description,
    status,
    metadata_json
)
VALUES
    (
        'SQLSERVER_SERVER_HOSTED_PROFILE',
        'SQL Server Server Hosted Profile',
        'SQLSERVER_DATABASE',
        'SERVER_HOSTED',
        'AFTER_SEAL',
        false,
        'Server-hosted SQL Server source captured after submission seal.',
        'ACTIVE',
        '{}'::jsonb
    ),
    (
        'SQLSERVER_STUDENT_DEVICE_LOCAL_PROFILE',
        'SQL Server Student Device Local Profile',
        'SQLSERVER_DATABASE',
        'STUDENT_DEVICE_LOCAL',
        'AFTER_SEAL',
        true,
        'Student-device-local SQL Server source; capture may require device-bound agent.',
        'ACTIVE',
        '{}'::jsonb
    ),
    (
        'MISA_SERVER_HOSTED_PROFILE',
        'MISA Server Hosted Profile',
        'MISA_DATABASE',
        'SERVER_HOSTED',
        'AFTER_SEAL',
        false,
        'Server-hosted MISA source captured after submission seal.',
        'ACTIVE',
        '{}'::jsonb
    ),
    (
        'MISA_STUDENT_DEVICE_LOCAL_PROFILE',
        'MISA Student Device Local Profile',
        'MISA_DATABASE',
        'STUDENT_DEVICE_LOCAL',
        'AFTER_SEAL',
        true,
        'Student-device-local MISA source; capture may require device-bound agent.',
        'ACTIVE',
        '{}'::jsonb
    ),
    (
        'AMIS_API_PROFILE',
        'AMIS API Profile',
        'AMIS_API',
        'EXTERNAL_SAAS',
        'AFTER_SEAL',
        false,
        'External AMIS API source captured asynchronously after seal.',
        'ACTIVE',
        '{}'::jsonb
    )
ON CONFLICT (profile_code)
DO UPDATE
SET
    profile_name = EXCLUDED.profile_name,
    source_type = EXCLUDED.source_type,
    source_location_mode = EXCLUDED.source_location_mode,
    default_capture_timing = EXCLUDED.default_capture_timing,
    requires_agent = EXCLUDED.requires_agent,
    description = EXCLUDED.description,
    status = EXCLUDED.status,
    metadata_json = EXCLUDED.metadata_json,
    updated_at = now();

WITH engine_mapping AS (
    SELECT
        p.capture_profile_id,
        ge.grading_engine_id,
        'SUPPORTED'::varchar(50) AS link_role
    FROM capture.capture_profile p
    JOIN grading.grading_engine ge
      ON (
            (p.profile_code IN ('SQLSERVER_SERVER_HOSTED_PROFILE', 'SQLSERVER_STUDENT_DEVICE_LOCAL_PROFILE')
             AND ge.engine_code = 'SQL_RESULT_COMPARATOR')
         OR (p.profile_code IN ('MISA_SERVER_HOSTED_PROFILE', 'MISA_STUDENT_DEVICE_LOCAL_PROFILE')
             AND ge.engine_code = 'MISA_DATABASE_COMPARATOR')
         OR (p.profile_code = 'AMIS_API_PROFILE'
             AND ge.engine_code = 'AMIS_API_DATA_COMPARATOR')
      )
)
INSERT INTO capture.capture_profile_engine_link (
    capture_profile_id,
    grading_engine_id,
    link_role,
    is_active,
    metadata_json
)
SELECT
    em.capture_profile_id,
    em.grading_engine_id,
    em.link_role,
    true,
    '{}'::jsonb
FROM engine_mapping em
ON CONFLICT (capture_profile_id, grading_engine_id, link_role)
DO UPDATE
SET
    is_active = EXCLUDED.is_active,
    metadata_json = EXCLUDED.metadata_json;

DROP VIEW IF EXISTS capture.v_capture_profile_summary;

CREATE VIEW capture.v_capture_profile_summary AS
SELECT
    cp.capture_profile_id,
    cp.profile_code,
    cp.profile_name,
    cp.source_type,
    cp.source_location_mode,
    cp.default_capture_timing,
    cp.requires_agent,
    cp.status,
    cp.created_at,
    cp.updated_at
FROM capture.capture_profile cp;

COMMENT ON VIEW capture.v_capture_profile_summary IS
    'Safe capture profile summary view without extractor query text or credential-like data.';

GRANT SELECT, INSERT, UPDATE ON TABLE capture.capture_profile TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE capture.capture_extractor_query TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE capture.capture_profile_engine_link TO exam_sys_app;

REVOKE DELETE ON TABLE capture.capture_profile FROM exam_sys_app;
REVOKE DELETE ON TABLE capture.capture_extractor_query FROM exam_sys_app;
REVOKE DELETE ON TABLE capture.capture_profile_engine_link FROM exam_sys_app;

REVOKE SELECT ON TABLE capture.capture_profile FROM exam_sys_readonly;
REVOKE SELECT ON TABLE capture.capture_extractor_query FROM exam_sys_readonly;
REVOKE SELECT ON TABLE capture.capture_profile_engine_link FROM exam_sys_readonly;

GRANT SELECT ON TABLE capture.v_capture_profile_summary TO exam_sys_app;
GRANT SELECT ON TABLE capture.v_capture_profile_summary TO exam_sys_readonly;
