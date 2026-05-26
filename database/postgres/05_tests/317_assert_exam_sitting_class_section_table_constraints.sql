-- Verifies delivery.exam_sitting_class_section table and unique constraint exist.

DO
$$
BEGIN
    IF to_regclass('delivery.exam_sitting_class_section') IS NULL THEN
        RAISE EXCEPTION 'Table delivery.exam_sitting_class_section does not exist';
    END IF;

    -- Verify columns exist
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'delivery'
          AND table_name = 'exam_sitting_class_section'
          AND column_name = 'exam_sitting_id'
    ) THEN
        RAISE EXCEPTION 'Column exam_sitting_id is missing from delivery.exam_sitting_class_section';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'delivery'
          AND table_name = 'exam_sitting_class_section'
          AND column_name = 'class_section_id'
    ) THEN
        RAISE EXCEPTION 'Column class_section_id is missing from delivery.exam_sitting_class_section';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'delivery'
          AND table_name = 'exam_sitting_class_section'
          AND constraint_name = 'uq_delivery_exam_sitting_class_section'
    ) THEN
        RAISE EXCEPTION 'Constraint uq_delivery_exam_sitting_class_section is missing';
    END IF;

    RAISE NOTICE 'PASS: delivery.exam_sitting_class_section table and unique constraint verified.';
END
$$;
