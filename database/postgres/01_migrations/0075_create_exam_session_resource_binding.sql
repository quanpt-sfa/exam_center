-- Phase 4.7.4 source: docs/phase_4_7_assessment_modality_grading_profile_foundation.md
-- Creates exam-session resource binding foundation for server-hosted and student-device-local resources.

CREATE TABLE IF NOT EXISTS delivery.exam_session_resource_binding (
    resource_binding_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_session_id bigint NOT NULL,
    student_id bigint NOT NULL,
    generated_exam_instance_id bigint NULL,
    capture_profile_id bigint NULL,
    device_id bigint NULL,
    station_id bigint NULL,
    resource_type varchar(50) NOT NULL,
    resource_location_mode varchar(50) NOT NULL,
    resource_code varchar(150) NOT NULL,
    resource_ref text NULL,
    connection_profile_ref text NULL,
    assigned_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz NULL,
    sealed_at timestamptz NULL,
    released_at timestamptz NULL,
    status varchar(30) NOT NULL DEFAULT 'ASSIGNED',
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT ck_del_esrb_resource_type CHECK (
        resource_type IN (
            'SQLSERVER_STUDENT_DB',
            'POSTGRES_STUDENT_DB',
            'MISA_DATABASE',
            'AMIS_TENANT',
            'FILE_WORKSPACE',
            'LOCAL_AGENT_WORKSPACE',
            'OTHER'
        )
    ),
    CONSTRAINT ck_del_esrb_resource_location_mode CHECK (
        resource_location_mode IN (
            'SERVER_HOSTED',
            'STUDENT_DEVICE_LOCAL',
            'EXTERNAL_SAAS',
            'MANUAL_UPLOAD',
            'MIXED'
        )
    ),
    CONSTRAINT ck_del_esrb_status CHECK (
        status IN ('ASSIGNED', 'ACTIVE', 'SEALED', 'RELEASED', 'FAILED', 'CANCELLED')
    ),
    CONSTRAINT ck_del_esrb_conn_profile_ref CHECK (
        connection_profile_ref IS NULL
        OR connection_profile_ref ~* '^(secret|vault|env|config)://'
    ),
    CONSTRAINT ck_del_esrb_student_local_device CHECK (
        resource_location_mode <> 'STUDENT_DEVICE_LOCAL'
        OR device_id IS NOT NULL
        OR status IN ('FAILED', 'CANCELLED')
    ),
    CONSTRAINT ck_del_esrb_external_saas_type CHECK (
        resource_location_mode <> 'EXTERNAL_SAAS'
        OR resource_type IN ('AMIS_TENANT', 'OTHER')
    ),
    CONSTRAINT ck_del_esrb_activated_at CHECK (
        activated_at IS NULL OR activated_at >= assigned_at
    ),
    CONSTRAINT ck_del_esrb_sealed_at CHECK (
        sealed_at IS NULL OR sealed_at >= COALESCE(activated_at, assigned_at)
    ),
    CONSTRAINT ck_del_esrb_released_at CHECK (
        released_at IS NULL OR released_at >= COALESCE(sealed_at, COALESCE(activated_at, assigned_at))
    ),
    CONSTRAINT ck_del_esrb_updated_at CHECK (
        updated_at IS NULL OR updated_at >= created_at
    ),
    CONSTRAINT fk_del_esrb_exam_session FOREIGN KEY (exam_session_id)
        REFERENCES delivery.exam_session(exam_session_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_del_esrb_student FOREIGN KEY (student_id)
        REFERENCES identity.student_profile(student_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_del_esrb_generated_instance FOREIGN KEY (generated_exam_instance_id)
        REFERENCES delivery.generated_exam_instance(generated_exam_instance_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_del_esrb_capture_profile FOREIGN KEY (capture_profile_id)
        REFERENCES capture.capture_profile(capture_profile_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_del_esrb_device FOREIGN KEY (device_id)
        REFERENCES facility.device(device_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_del_esrb_station FOREIGN KEY (station_id)
        REFERENCES facility.lab_station(station_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_del_esrb_exam_session_id
    ON delivery.exam_session_resource_binding (exam_session_id);

CREATE INDEX IF NOT EXISTS idx_del_esrb_student_id
    ON delivery.exam_session_resource_binding (student_id);

CREATE INDEX IF NOT EXISTS idx_del_esrb_generated_instance_id
    ON delivery.exam_session_resource_binding (generated_exam_instance_id);

CREATE INDEX IF NOT EXISTS idx_del_esrb_capture_profile_id
    ON delivery.exam_session_resource_binding (capture_profile_id);

CREATE INDEX IF NOT EXISTS idx_del_esrb_device_id
    ON delivery.exam_session_resource_binding (device_id);

CREATE INDEX IF NOT EXISTS idx_del_esrb_station_id
    ON delivery.exam_session_resource_binding (station_id);

CREATE INDEX IF NOT EXISTS idx_del_esrb_resource_type
    ON delivery.exam_session_resource_binding (resource_type);

CREATE INDEX IF NOT EXISTS idx_del_esrb_resource_location_mode
    ON delivery.exam_session_resource_binding (resource_location_mode);

CREATE INDEX IF NOT EXISTS idx_del_esrb_status
    ON delivery.exam_session_resource_binding (status);

CREATE UNIQUE INDEX IF NOT EXISTS ux_del_esrb_active_session_type_code
    ON delivery.exam_session_resource_binding (exam_session_id, resource_type, resource_code)
    WHERE status IN ('ASSIGNED', 'ACTIVE', 'SEALED');

DROP VIEW IF EXISTS delivery.v_exam_session_resource_binding_summary;

CREATE VIEW delivery.v_exam_session_resource_binding_summary AS
SELECT
    rb.resource_binding_id,
    rb.exam_session_id,
    rb.student_id,
    rb.generated_exam_instance_id,
    rb.capture_profile_id,
    cp.profile_code,
    rb.device_id,
    rb.station_id,
    rb.resource_type,
    rb.resource_location_mode,
    rb.resource_code,
    rb.assigned_at,
    rb.activated_at,
    rb.sealed_at,
    rb.released_at,
    rb.status
FROM delivery.exam_session_resource_binding rb
LEFT JOIN capture.capture_profile cp
    ON cp.capture_profile_id = rb.capture_profile_id;

COMMENT ON VIEW delivery.v_exam_session_resource_binding_summary IS
    'Safe summary of exam session resource binding without connection refs, resource refs, or metadata payloads.';

GRANT SELECT, INSERT, UPDATE ON TABLE delivery.exam_session_resource_binding TO exam_sys_app;
REVOKE DELETE ON TABLE delivery.exam_session_resource_binding FROM exam_sys_app;

REVOKE SELECT ON TABLE delivery.exam_session_resource_binding FROM exam_sys_readonly;
GRANT SELECT ON TABLE delivery.v_exam_session_resource_binding_summary TO exam_sys_readonly;
GRANT SELECT ON TABLE delivery.v_exam_session_resource_binding_summary TO exam_sys_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_readonly;
