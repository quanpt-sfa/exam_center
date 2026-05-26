INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    (
        '0130_add_submission_history_contract.sql',
        'Add submission.submission_history table for Phase 2E backend lifecycle audit',
        NULL,
        current_user
    ),
    (
        '0131_record_submission_history_contract_versions.sql',
        'Record Phase 2E submission history contract migration versions',
        NULL,
        current_user
    )
ON CONFLICT (version) DO NOTHING;