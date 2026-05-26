INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    (
        '0136_add_generated_question_original_linkage_foundation.sql',
        'Add generated question original-link, ordering, variant, render-hash, and grading-profile snapshot foundation',
        NULL,
        current_user
    ),
    (
        '0137_record_generated_question_original_linkage_foundation_versions.sql',
        'Record generated question original-link foundation migration versions',
        NULL,
        current_user
    )
ON CONFLICT (version) DO NOTHING;