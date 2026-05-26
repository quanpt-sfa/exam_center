INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    (
        '0132_allow_sealed_file_ref_in_question_grading_profile.sql',
        'Allow SEALED_FILE_REF in assessment.question_grading_profile.input_source for file-upload answer workflow',
        NULL,
        current_user
    ),
    (
        '0133_record_allow_sealed_file_ref_in_question_grading_profile_versions.sql',
        'Record SEALED_FILE_REF question_grading_profile contract migration versions',
        NULL,
        current_user
    )
ON CONFLICT (version) DO NOTHING;