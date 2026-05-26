-- Verifies assessment.exam.class_section_id is nullable (authoring decoupled from class sections).

DO
$$
BEGIN
    IF to_regclass('assessment.exam') IS NULL THEN
        RAISE EXCEPTION 'Table assessment.exam does not exist';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'assessment'
          AND table_name = 'exam'
          AND column_name = 'class_section_id'
          AND is_nullable = 'YES'
    ) THEN
        RAISE EXCEPTION 'Column assessment.exam.class_section_id must be nullable after decoupling';
    END IF;

    RAISE NOTICE 'PASS: assessment.exam.class_section_id is nullable.';
END
$$;
