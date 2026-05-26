INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    (
        '0134_add_python_grading_contract_foundation.sql',
        'Add additive Python auto-grading contract values and assessment.python_test_case foundation table',
        NULL,
        current_user
    ),
    (
        '0135_record_python_grading_contract_foundation_versions.sql',
        'Record Python auto-grading contract foundation migration versions',
        NULL,
        current_user
    )
ON CONFLICT (version) DO NOTHING;