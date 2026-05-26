-- Phase 3.2.1 source: docs/phase_2_assessment_generator_pipeline.md
-- Creates immutable generated exam instance snapshot per exam session.

CREATE TABLE IF NOT EXISTS delivery.generated_exam_instance (
    generated_exam_instance_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_session_id bigint NOT NULL,
    exam_version_id bigint NOT NULL,
    blueprint_id bigint NULL,
    generation_mode varchar(50) NOT NULL,
    generation_status varchar(30) NOT NULL,
    generation_seed varchar(255) NULL,
    generation_seed_hash char(64) NULL,
    generator_name varchar(100) NULL,
    generator_version varchar(100) NULL,
    snapshot_version integer NOT NULL DEFAULT 1,
    instance_hash char(64) NULL,
    generated_at timestamptz NULL,
    generated_by bigint NULL,
    voided_at timestamptz NULL,
    voided_by bigint NULL,
    void_reason text NULL,
    metadata_json jsonb NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_delivery_generated_exam_instance_exam_session UNIQUE (exam_session_id),
    CONSTRAINT ck_delivery_generated_exam_instance_snapshot_version CHECK (snapshot_version > 0),
    CONSTRAINT ck_delivery_generated_exam_instance_mode CHECK (
        generation_mode IN ('FIXED', 'RANDOM_FROM_BANK', 'PARAMETERIZED', 'HYBRID')
    ),
    CONSTRAINT ck_delivery_generated_exam_instance_status CHECK (
        generation_status IN ('PENDING', 'GENERATED', 'FAILED', 'VOIDED')
    ),
    CONSTRAINT ck_delivery_generated_exam_instance_generated_at CHECK (
        generation_status <> 'GENERATED' OR generated_at IS NOT NULL
    ),
    CONSTRAINT ck_delivery_generated_exam_instance_voided_fields CHECK (
        generation_status <> 'VOIDED' OR (voided_at IS NOT NULL AND voided_by IS NOT NULL)
    ),
    CONSTRAINT ck_delivery_generated_exam_instance_updated_at CHECK (
        updated_at IS NULL OR updated_at >= created_at
    ),
    CONSTRAINT fk_delivery_generated_exam_instance_exam_session FOREIGN KEY (exam_session_id)
        REFERENCES delivery.exam_session(exam_session_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_generated_exam_instance_exam_version FOREIGN KEY (exam_version_id)
        REFERENCES assessment.exam_version(exam_version_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_generated_exam_instance_blueprint FOREIGN KEY (blueprint_id)
        REFERENCES assessment.exam_blueprint(blueprint_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_delivery_generated_exam_instance_generated_by FOREIGN KEY (generated_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_delivery_generated_exam_instance_voided_by FOREIGN KEY (voided_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

COMMENT ON TABLE delivery.generated_exam_instance IS
'Immutable generated exam snapshot per exam_session. Reconnect/reload/device-transfer must reuse the same generated instance.';

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_instance_exam_version_id
    ON delivery.generated_exam_instance (exam_version_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_instance_blueprint_id
    ON delivery.generated_exam_instance (blueprint_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_instance_generation_status
    ON delivery.generated_exam_instance (generation_status);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_instance_generated_by
    ON delivery.generated_exam_instance (generated_by);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_instance_voided_by
    ON delivery.generated_exam_instance (voided_by);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_instance_generated_at
    ON delivery.generated_exam_instance (generated_at);

GRANT SELECT, INSERT, UPDATE ON TABLE delivery.generated_exam_instance TO exam_sys_app;

-- Generated instance metadata is sensitive; do not expose broadly.
REVOKE SELECT ON TABLE delivery.generated_exam_instance FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_readonly;
