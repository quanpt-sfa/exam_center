-- Visual paper asset foundation for exam version delivery.
-- Stores auditable metadata only; file bytes remain outside PostgreSQL.

CREATE TABLE IF NOT EXISTS assessment.exam_version_paper_asset (
    paper_asset_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_version_id bigint NOT NULL,
    asset_kind varchar(30) NOT NULL,
    original_filename varchar(500) NOT NULL,
    stored_filename varchar(500) NOT NULL,
    storage_relative_path text NOT NULL,
    mime_type varchar(100) NOT NULL,
    file_size_bytes bigint NOT NULL,
    sha256_hash char(64) NOT NULL,
    page_count integer NULL,
    render_status varchar(30) NOT NULL DEFAULT 'UPLOADED',
    is_active boolean NOT NULL DEFAULT true,
    created_by bigint NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    retired_at timestamptz NULL,
    retired_by bigint NULL,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT ck_assessment_evpa_asset_kind CHECK (
        asset_kind IN ('PDF_SOURCE', 'IMAGE_PAGE', 'IMAGE_PAGE_SET')
    ),
    CONSTRAINT ck_assessment_evpa_render_status CHECK (
        render_status IN ('UPLOADED', 'RENDERED', 'FAILED', 'RETIRED')
    ),
    CONSTRAINT ck_assessment_evpa_file_size_bytes CHECK (
        file_size_bytes > 0
    ),
    CONSTRAINT ck_assessment_evpa_page_count CHECK (
        page_count IS NULL OR page_count > 0
    ),
    CONSTRAINT ck_assessment_evpa_mime_type CHECK (
        mime_type IN ('application/pdf', 'image/png', 'image/jpeg', 'image/webp')
    ),
    CONSTRAINT fk_assessment_evpa_exam_version FOREIGN KEY (exam_version_id)
        REFERENCES assessment.exam_version(exam_version_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_assessment_evpa_created_by FOREIGN KEY (created_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_assessment_evpa_retired_by FOREIGN KEY (retired_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

COMMENT ON TABLE assessment.exam_version_paper_asset IS
    'Audit metadata for visual exam paper assets linked to assessment.exam_version. File bytes are stored externally.';

CREATE INDEX IF NOT EXISTS idx_assessment_evpa_exam_version_id
    ON assessment.exam_version_paper_asset (exam_version_id);

CREATE INDEX IF NOT EXISTS idx_assessment_evpa_sha256_hash
    ON assessment.exam_version_paper_asset (sha256_hash);

CREATE INDEX IF NOT EXISTS idx_assessment_evpa_is_active
    ON assessment.exam_version_paper_asset (is_active);

CREATE INDEX IF NOT EXISTS idx_assessment_evpa_render_status
    ON assessment.exam_version_paper_asset (render_status);

CREATE UNIQUE INDEX IF NOT EXISTS ux_assessment_evpa_one_active_source_per_version
    ON assessment.exam_version_paper_asset (exam_version_id)
    WHERE is_active
      AND asset_kind IN ('PDF_SOURCE', 'IMAGE_PAGE_SET');

CREATE OR REPLACE VIEW assessment.v_exam_version_paper_asset_admin_summary AS
SELECT
    paper_asset_id,
    exam_version_id,
    asset_kind,
    original_filename,
    mime_type,
    file_size_bytes,
    sha256_hash,
    page_count,
    render_status,
    is_active,
    created_by,
    created_at,
    retired_at,
    retired_by,
    metadata_json
FROM assessment.exam_version_paper_asset;

COMMENT ON VIEW assessment.v_exam_version_paper_asset_admin_summary IS
    'Safe summary for visual exam paper assets without storage file/path references.';

GRANT SELECT, INSERT, UPDATE ON TABLE assessment.exam_version_paper_asset TO exam_sys_app;
REVOKE DELETE ON TABLE assessment.exam_version_paper_asset FROM exam_sys_app;

REVOKE SELECT ON TABLE assessment.exam_version_paper_asset FROM exam_sys_readonly;

GRANT SELECT ON TABLE assessment.v_exam_version_paper_asset_admin_summary TO exam_sys_app;
GRANT SELECT ON TABLE assessment.v_exam_version_paper_asset_admin_summary TO exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assessment TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assessment TO exam_sys_readonly;
