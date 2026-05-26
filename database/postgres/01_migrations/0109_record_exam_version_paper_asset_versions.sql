-- Records visual paper asset foundation migration metadata.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    (
        '0108_create_exam_version_paper_asset.sql',
        'Create assessment.exam_version_paper_asset table, safe admin summary view, and access hardening',
        NULL,
        current_user
    ),
    (
        '0109_record_exam_version_paper_asset_versions.sql',
        'Record visual paper asset foundation migration versions',
        NULL,
        current_user
    )
ON CONFLICT (version) DO NOTHING;
