-- Phase 4.7.3 source: docs/phase_4_7_assessment_modality_grading_profile_foundation.md
-- Creates exam-version delivery profile foundation for modality and primary answer source configuration.

CREATE TABLE IF NOT EXISTS assessment.exam_version_delivery_profile (
    exam_version_delivery_profile_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_version_id bigint NOT NULL,
    delivery_mode varchar(50) NOT NULL,
    work_mode varchar(50) NOT NULL DEFAULT 'INDIVIDUAL',
    primary_answer_source varchar(50) NOT NULL,
    requires_capture boolean NOT NULL DEFAULT false,
    capture_timing varchar(50) NOT NULL DEFAULT 'NONE',
    default_capture_profile_id bigint NULL,
    default_grading_engine_id bigint NULL,
    allow_mixed_question_sources boolean NOT NULL DEFAULT false,
    form_autosave_enabled boolean NOT NULL DEFAULT true,
    database_work_mode varchar(50) NOT NULL DEFAULT 'NONE',
    status varchar(30) NOT NULL DEFAULT 'DRAFT',
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_assessment_exam_version_delivery_profile_exam_version UNIQUE (exam_version_id),
    CONSTRAINT ck_assessment_exam_version_delivery_profile_delivery_mode CHECK (
        delivery_mode IN (
            'FORM_BASED',
            'DATABASE_BASED',
            'EXTERNAL_SYSTEM_BASED',
            'FILE_BASED',
            'MIXED'
        )
    ),
    CONSTRAINT ck_assessment_exam_version_delivery_profile_work_mode CHECK (
        work_mode IN ('INDIVIDUAL', 'GROUP')
    ),
    CONSTRAINT ck_assessment_exam_version_delivery_profile_primary_source CHECK (
        primary_answer_source IN (
            'SEALED_FORM_ANSWER',
            'STUDENT_DATABASE',
            'MISA_DATABASE',
            'AMIS_API',
            'FILE_ARTIFACT',
            'MIXED',
            'MANUAL'
        )
    ),
    CONSTRAINT ck_assessment_exam_version_delivery_profile_capture_timing CHECK (
        capture_timing IN ('NONE', 'AFTER_SEAL', 'MANUAL_UPLOAD_AFTER_SEAL')
    ),
    CONSTRAINT ck_assessment_exam_version_delivery_profile_database_work_mode CHECK (
        database_work_mode IN (
            'NONE',
            'SERVER_HOSTED',
            'STUDENT_DEVICE_LOCAL',
            'EXTERNAL_SAAS',
            'MANUAL_UPLOAD',
            'MIXED'
        )
    ),
    CONSTRAINT ck_assessment_exam_version_delivery_profile_status CHECK (
        status IN ('DRAFT', 'ACTIVE', 'RETIRED', 'DISABLED')
    ),
    CONSTRAINT ck_assessment_exam_version_delivery_profile_capture_consistency CHECK (
        (NOT requires_capture AND capture_timing = 'NONE')
        OR (requires_capture AND capture_timing <> 'NONE')
    ),
    CONSTRAINT ck_assessment_exam_version_delivery_profile_form_source_practical CHECK (
        delivery_mode <> 'FORM_BASED'
        OR primary_answer_source IN ('SEALED_FORM_ANSWER', 'MIXED', 'MANUAL')
    ),
    CONSTRAINT ck_assessment_exam_version_delivery_profile_database_mode_practical CHECK (
        NOT (
            delivery_mode = 'DATABASE_BASED'
            AND database_work_mode = 'NONE'
            AND primary_answer_source IN ('STUDENT_DATABASE', 'MISA_DATABASE')
        )
    ),
    CONSTRAINT ck_assessment_exam_version_delivery_profile_updated_at CHECK (
        updated_at IS NULL OR updated_at >= created_at
    ),
    CONSTRAINT fk_assessment_exam_version_delivery_profile_exam_version FOREIGN KEY (exam_version_id)
        REFERENCES assessment.exam_version(exam_version_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_assessment_exam_version_delivery_profile_default_capture_profile FOREIGN KEY (default_capture_profile_id)
        REFERENCES capture.capture_profile(capture_profile_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_assessment_exam_version_delivery_profile_default_grading_engine FOREIGN KEY (default_grading_engine_id)
        REFERENCES grading.grading_engine(grading_engine_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_version_delivery_profile_exam_version_id
    ON assessment.exam_version_delivery_profile (exam_version_id);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_version_delivery_profile_default_capture_profile_id
    ON assessment.exam_version_delivery_profile (default_capture_profile_id);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_version_delivery_profile_default_grading_engine_id
    ON assessment.exam_version_delivery_profile (default_grading_engine_id);

CREATE OR REPLACE VIEW assessment.v_exam_version_delivery_profile_summary AS
SELECT
    evdp.exam_version_delivery_profile_id,
    evdp.exam_version_id,
    evdp.delivery_mode,
    evdp.work_mode,
    evdp.primary_answer_source,
    evdp.requires_capture,
    evdp.capture_timing,
    cp.profile_code AS default_capture_profile_code,
    ge.engine_code AS default_grading_engine_code,
    evdp.allow_mixed_question_sources,
    evdp.form_autosave_enabled,
    evdp.database_work_mode,
    evdp.status,
    evdp.created_at,
    evdp.updated_at
FROM assessment.exam_version_delivery_profile evdp
LEFT JOIN capture.capture_profile cp
    ON cp.capture_profile_id = evdp.default_capture_profile_id
LEFT JOIN grading.grading_engine ge
    ON ge.grading_engine_id = evdp.default_grading_engine_id;

COMMENT ON VIEW assessment.v_exam_version_delivery_profile_summary IS
    'Safe summary of exam version delivery profile with profile/engine codes and no secret payloads.';

GRANT SELECT, INSERT, UPDATE ON TABLE assessment.exam_version_delivery_profile TO exam_sys_app;
REVOKE DELETE ON TABLE assessment.exam_version_delivery_profile FROM exam_sys_app;

REVOKE SELECT ON TABLE assessment.exam_version_delivery_profile FROM exam_sys_readonly;

GRANT SELECT ON TABLE assessment.v_exam_version_delivery_profile_summary TO exam_sys_app;
GRANT SELECT ON TABLE assessment.v_exam_version_delivery_profile_summary TO exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assessment TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assessment TO exam_sys_readonly;
