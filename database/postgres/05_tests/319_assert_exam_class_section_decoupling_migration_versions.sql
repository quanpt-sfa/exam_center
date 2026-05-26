-- Verifies migration metadata includes the exam/class-section decoupling and
-- multi-class-section sitting migrations.

DO
$$
DECLARE
    missing_versions text := '';
    expected text[] := ARRAY[
        '0140_make_exam_class_section_nullable.sql',
        '0141_record_make_exam_class_section_nullable_versions.sql',
        '0142_create_exam_sitting_class_section.sql',
        '0143_record_create_exam_sitting_class_section_versions.sql'
    ];
    v text;
BEGIN
    FOREACH v IN ARRAY expected
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM app_meta.schema_migrations WHERE version = v
        ) THEN
            missing_versions := missing_versions
                || CASE WHEN missing_versions = '' THEN '' ELSE ', ' END
                || v;
        END IF;
    END LOOP;

    IF missing_versions <> '' THEN
        RAISE EXCEPTION 'Missing exam/class-section decoupling migration versions: %', missing_versions;
    END IF;

    RAISE NOTICE 'PASS: exam/class-section decoupling migration versions are recorded.';
END
$$;
