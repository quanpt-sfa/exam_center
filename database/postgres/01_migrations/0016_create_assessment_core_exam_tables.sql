-- Phase 2.1 source: docs/phase_2_assessment_generator_pipeline.md
-- Creates assessment core tables: assessment_type, exam, exam_version.

CREATE TABLE IF NOT EXISTS assessment.assessment_type (
    assessment_type_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    type_code varchar(50) NOT NULL,
    type_name varchar(255) NOT NULL,
    description text NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_assessment_assessment_type_type_code UNIQUE (type_code),
    CONSTRAINT ck_assessment_assessment_type_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS assessment.exam (
    exam_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    class_section_id bigint NOT NULL,
    assessment_type_id bigint NOT NULL,
    exam_code varchar(100) NOT NULL,
    exam_name varchar(255) NOT NULL,
    description text NULL,
    exam_status varchar(30) NOT NULL,
    created_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_assessment_exam_exam_code UNIQUE (exam_code),
    CONSTRAINT ck_assessment_exam_status CHECK (exam_status IN ('DRAFT', 'READY', 'ACTIVE', 'CLOSED', 'ARCHIVED', 'CANCELLED')),
    CONSTRAINT ck_assessment_exam_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at),
    CONSTRAINT fk_assessment_exam_class_section FOREIGN KEY (class_section_id)
        REFERENCES academic.class_section(class_section_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_assessment_exam_assessment_type FOREIGN KEY (assessment_type_id)
        REFERENCES assessment.assessment_type(assessment_type_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_assessment_exam_created_by FOREIGN KEY (created_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS assessment.exam_version (
    exam_version_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_id bigint NOT NULL,
    version_no integer NOT NULL,
    version_label varchar(100) NULL,
    duration_seconds integer NOT NULL,
    total_score numeric(10,2) NOT NULL,
    shuffle_questions boolean NOT NULL DEFAULT false,
    shuffle_options boolean NOT NULL DEFAULT false,
    randomization_mode varchar(50) NOT NULL,
    status varchar(30) NOT NULL,
    published_at timestamptz NULL,
    published_by bigint NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_assessment_exam_version_exam_version_no UNIQUE (exam_id, version_no),
    CONSTRAINT ck_assessment_exam_version_duration_seconds CHECK (duration_seconds > 0),
    CONSTRAINT ck_assessment_exam_version_total_score CHECK (total_score > 0),
    CONSTRAINT ck_assessment_exam_version_randomization_mode CHECK (
        randomization_mode IN ('FIXED', 'RANDOM_FROM_BANK', 'PARAMETERIZED', 'HYBRID')
    ),
    CONSTRAINT ck_assessment_exam_version_status CHECK (
        status IN ('DRAFT', 'UNDER_REVIEW', 'PUBLISHED', 'RETIRED', 'VOIDED')
    ),
    CONSTRAINT ck_assessment_exam_version_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at),
    CONSTRAINT fk_assessment_exam_version_exam FOREIGN KEY (exam_id)
        REFERENCES assessment.exam(exam_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_assessment_exam_version_published_by FOREIGN KEY (published_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_class_section_id
    ON assessment.exam (class_section_id);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_assessment_type_id
    ON assessment.exam (assessment_type_id);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_created_by
    ON assessment.exam (created_by);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_version_exam_id
    ON assessment.exam_version (exam_id);

CREATE INDEX IF NOT EXISTS idx_assessment_exam_version_published_by
    ON assessment.exam_version (published_by);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE assessment.assessment_type TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE assessment.exam TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE assessment.exam_version TO exam_sys_app;

GRANT SELECT ON TABLE assessment.assessment_type TO exam_sys_readonly;
GRANT SELECT ON TABLE assessment.exam TO exam_sys_readonly;
GRANT SELECT ON TABLE assessment.exam_version TO exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assessment TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assessment TO exam_sys_readonly;