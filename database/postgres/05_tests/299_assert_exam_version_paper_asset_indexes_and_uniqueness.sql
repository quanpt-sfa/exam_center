-- Verifies indexes and active-source uniqueness policy for visual paper assets.

DO
$$
DECLARE
    missing_indexes text := '';
    predicate_sql text;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'assessment'
          AND indexname = 'idx_assessment_evpa_exam_version_id'
    ) THEN
        missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || 'idx_assessment_evpa_exam_version_id';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'assessment'
          AND indexname = 'idx_assessment_evpa_sha256_hash'
    ) THEN
        missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || 'idx_assessment_evpa_sha256_hash';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'assessment'
          AND indexname = 'idx_assessment_evpa_is_active'
    ) THEN
        missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || 'idx_assessment_evpa_is_active';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'assessment'
          AND indexname = 'idx_assessment_evpa_render_status'
    ) THEN
        missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || 'idx_assessment_evpa_render_status';
    END IF;

    IF missing_indexes <> '' THEN
        RAISE EXCEPTION 'Missing visual paper asset indexes: %', missing_indexes;
    END IF;

    SELECT pg_get_expr(i.indpred, i.indrelid)
    INTO predicate_sql
    FROM pg_index i
    JOIN pg_class c
      ON c.oid = i.indexrelid
    JOIN pg_namespace n
      ON n.oid = c.relnamespace
    WHERE n.nspname = 'assessment'
      AND c.relname = 'ux_assessment_evpa_one_active_source_per_version';

    IF predicate_sql IS NULL THEN
        RAISE EXCEPTION 'Missing unique partial index ux_assessment_evpa_one_active_source_per_version';
    END IF;

    IF predicate_sql NOT ILIKE '%is_active%'
       OR predicate_sql NOT ILIKE '%PDF_SOURCE%'
       OR predicate_sql NOT ILIKE '%IMAGE_PAGE_SET%' THEN
        RAISE EXCEPTION 'Unexpected uniqueness predicate for active source asset: %', predicate_sql;
    END IF;

    RAISE NOTICE 'PASS: visual paper asset index and uniqueness policy are valid.';
END
$$;
