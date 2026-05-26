-- Records student answer file attachment foundation migration metadata.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    (
        '0110_create_submission_answer_file_asset.sql',
        'Create submission.answer_file_asset table, safe summary view, indexes, and access hardening',
        NULL,
        current_user
    ),
    (
        '0111_record_submission_answer_file_asset_versions.sql',
        'Record student answer file attachment foundation migration versions',
        NULL,
        current_user
    )
ON CONFLICT (version) DO NOTHING;

