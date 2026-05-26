-- Phase 3.0.2 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Adds identity photo history for exam identity verification.

CREATE TABLE IF NOT EXISTS identity.person_photo (
    person_photo_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    person_id bigint NOT NULL,
    photo_ref text NOT NULL,
    photo_hash char(64) NULL,
    photo_type varchar(50) NOT NULL,
    is_current boolean NOT NULL DEFAULT false,
    valid_from timestamptz NOT NULL DEFAULT now(),
    valid_to timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by bigint NULL,
    CONSTRAINT ck_identity_person_photo_type CHECK (
        photo_type IN ('STUDENT_CARD', 'PROFILE', 'ID_VERIFICATION', 'IMPORT')
    ),
    CONSTRAINT ck_identity_person_photo_valid_range CHECK (valid_to IS NULL OR valid_to > valid_from),
    CONSTRAINT fk_identity_person_photo_person FOREIGN KEY (person_id)
        REFERENCES identity.person(person_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_identity_person_photo_created_by FOREIGN KEY (created_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_identity_person_photo_active_current_per_person
    ON identity.person_photo (person_id)
    WHERE is_current = true AND valid_to IS NULL;

CREATE INDEX IF NOT EXISTS idx_identity_person_photo_person_id
    ON identity.person_photo (person_id);

CREATE INDEX IF NOT EXISTS idx_identity_person_photo_created_by
    ON identity.person_photo (created_by);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE identity.person_photo TO exam_sys_app;

-- Restrict direct readonly access to person photo records.
REVOKE SELECT ON TABLE identity.person_photo FROM exam_sys_readonly;

GRANT USAGE, SELECT ON SEQUENCE identity.person_photo_person_photo_id_seq TO exam_sys_app;
REVOKE USAGE, SELECT ON SEQUENCE identity.person_photo_person_photo_id_seq FROM exam_sys_readonly;