-- Verifies key constraints for visual paper asset metadata safety and integrity.

DO
$$
DECLARE
    missing_constraints text := '';
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints tc
        WHERE tc.table_schema = 'assessment'
          AND tc.table_name = 'exam_version_paper_asset'
          AND tc.constraint_type = 'PRIMARY KEY'
    ) THEN
        missing_constraints := missing_constraints || CASE WHEN missing_constraints = '' THEN '' ELSE ', ' END || 'primary key';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.check_constraints cc
        JOIN information_schema.table_constraints tc
          ON tc.constraint_name = cc.constraint_name
         AND tc.constraint_schema = cc.constraint_schema
        WHERE tc.table_schema = 'assessment'
          AND tc.table_name = 'exam_version_paper_asset'
          AND tc.constraint_name = 'ck_assessment_evpa_file_size_bytes'
    ) THEN
        missing_constraints := missing_constraints || CASE WHEN missing_constraints = '' THEN '' ELSE ', ' END || 'ck_assessment_evpa_file_size_bytes';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.check_constraints cc
        JOIN information_schema.table_constraints tc
          ON tc.constraint_name = cc.constraint_name
         AND tc.constraint_schema = cc.constraint_schema
        WHERE tc.table_schema = 'assessment'
          AND tc.table_name = 'exam_version_paper_asset'
          AND tc.constraint_name = 'ck_assessment_evpa_page_count'
    ) THEN
        missing_constraints := missing_constraints || CASE WHEN missing_constraints = '' THEN '' ELSE ', ' END || 'ck_assessment_evpa_page_count';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.check_constraints cc
        JOIN information_schema.table_constraints tc
          ON tc.constraint_name = cc.constraint_name
         AND tc.constraint_schema = cc.constraint_schema
        WHERE tc.table_schema = 'assessment'
          AND tc.table_name = 'exam_version_paper_asset'
          AND tc.constraint_name = 'ck_assessment_evpa_mime_type'
    ) THEN
        missing_constraints := missing_constraints || CASE WHEN missing_constraints = '' THEN '' ELSE ', ' END || 'ck_assessment_evpa_mime_type';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.check_constraints cc
        JOIN information_schema.table_constraints tc
          ON tc.constraint_name = cc.constraint_name
         AND tc.constraint_schema = cc.constraint_schema
        WHERE tc.table_schema = 'assessment'
          AND tc.table_name = 'exam_version_paper_asset'
          AND tc.constraint_name = 'ck_assessment_evpa_asset_kind'
    ) THEN
        missing_constraints := missing_constraints || CASE WHEN missing_constraints = '' THEN '' ELSE ', ' END || 'ck_assessment_evpa_asset_kind';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.check_constraints cc
        JOIN information_schema.table_constraints tc
          ON tc.constraint_name = cc.constraint_name
         AND tc.constraint_schema = cc.constraint_schema
        WHERE tc.table_schema = 'assessment'
          AND tc.table_name = 'exam_version_paper_asset'
          AND tc.constraint_name = 'ck_assessment_evpa_render_status'
    ) THEN
        missing_constraints := missing_constraints || CASE WHEN missing_constraints = '' THEN '' ELSE ', ' END || 'ck_assessment_evpa_render_status';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints tc
        WHERE tc.table_schema = 'assessment'
          AND tc.table_name = 'exam_version_paper_asset'
          AND tc.constraint_name = 'fk_assessment_evpa_exam_version'
          AND tc.constraint_type = 'FOREIGN KEY'
    ) THEN
        missing_constraints := missing_constraints || CASE WHEN missing_constraints = '' THEN '' ELSE ', ' END || 'fk_assessment_evpa_exam_version';
    END IF;

    IF missing_constraints <> '' THEN
        RAISE EXCEPTION 'Missing visual paper asset constraints: %', missing_constraints;
    END IF;

    RAISE NOTICE 'PASS: visual paper asset constraints exist.';
END
$$;
