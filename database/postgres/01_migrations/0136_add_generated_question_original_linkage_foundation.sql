ALTER TABLE delivery.generated_exam_question
    ADD COLUMN IF NOT EXISTS original_question_id bigint NULL,
    ADD COLUMN IF NOT EXISTS source_exam_question_id bigint NULL,
    ADD COLUMN IF NOT EXISTS canonical_section_order integer NULL,
    ADD COLUMN IF NOT EXISTS canonical_question_order integer NULL,
    ADD COLUMN IF NOT EXISTS display_question_order integer NULL,
    ADD COLUMN IF NOT EXISTS variant_code varchar(100) NULL,
    ADD COLUMN IF NOT EXISTS variant_parameters_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS rendered_question_hash varchar(64) NULL,
    ADD COLUMN IF NOT EXISTS question_grading_profile_id bigint NULL;

ALTER TABLE delivery.generated_exam_question
    DROP CONSTRAINT IF EXISTS fk_delivery_generated_exam_question_original_question;

ALTER TABLE delivery.generated_exam_question
    ADD CONSTRAINT fk_delivery_generated_exam_question_original_question
    FOREIGN KEY (original_question_id)
    REFERENCES assessment.question_template(question_template_id)
    ON DELETE RESTRICT;

ALTER TABLE delivery.generated_exam_question
    DROP CONSTRAINT IF EXISTS fk_delivery_generated_exam_question_grading_profile;

ALTER TABLE delivery.generated_exam_question
    ADD CONSTRAINT fk_delivery_generated_exam_question_grading_profile
    FOREIGN KEY (question_grading_profile_id)
    REFERENCES assessment.question_grading_profile(question_grading_profile_id)
    ON DELETE RESTRICT;

UPDATE delivery.generated_exam_question
SET
    original_question_id = COALESCE(
        CASE
            WHEN coalesce(metadata_json->>'original_question_id', '') ~ '^[0-9]+$'
                THEN (metadata_json->>'original_question_id')::bigint
            ELSE NULL
        END,
        question_template_id
    ),
    source_exam_question_id = CASE
        WHEN coalesce(metadata_json->>'source_exam_question_id', '') ~ '^[0-9]+$'
            THEN (metadata_json->>'source_exam_question_id')::bigint
        ELSE source_exam_question_id
    END,
    canonical_section_order = COALESCE(
        canonical_section_order,
        CASE
            WHEN coalesce(metadata_json->>'canonical_section_order', '') ~ '^[0-9]+$'
                THEN (metadata_json->>'canonical_section_order')::integer
            ELSE 1
        END
    ),
    canonical_question_order = COALESCE(
        canonical_question_order,
        CASE
            WHEN coalesce(metadata_json->>'canonical_question_order', '') ~ '^[0-9]+$'
                THEN (metadata_json->>'canonical_question_order')::integer
            WHEN coalesce(metadata_json->>'question_no', '') ~ '^[0-9]+$'
                THEN (metadata_json->>'question_no')::integer
            ELSE question_order
        END
    ),
    display_question_order = COALESCE(display_question_order, question_order),
    variant_code = COALESCE(nullif(metadata_json->>'variant_code', ''), variant_code),
    variant_parameters_json = CASE
        WHEN jsonb_typeof(metadata_json->'variant_parameters') = 'object'
            THEN metadata_json->'variant_parameters'
        ELSE variant_parameters_json
    END,
    rendered_question_hash = COALESCE(
        rendered_question_hash,
        md5(coalesce(rendered_question_text, '') || '|' || coalesce(rendered_question_payload_json::text, ''))
    );

UPDATE delivery.generated_exam_question geq
SET question_grading_profile_id = sub.question_grading_profile_id
FROM (
    SELECT geq_inner.generated_exam_question_id, profile.question_grading_profile_id
    FROM delivery.generated_exam_question geq_inner
    JOIN delivery.generated_exam_instance gei
      ON gei.generated_exam_instance_id = geq_inner.generated_exam_instance_id
    JOIN LATERAL (
        SELECT p.question_grading_profile_id
        FROM assessment.question_grading_profile p
        WHERE p.question_template_id = geq_inner.question_template_id
          AND p.status IN ('ACTIVE', 'DRAFT')
          AND (
            p.exam_version_id = gei.exam_version_id
            OR p.exam_version_id IS NULL
          )
        ORDER BY
            CASE WHEN p.exam_version_id = gei.exam_version_id THEN 0 ELSE 1 END,
            CASE WHEN p.status = 'ACTIVE' THEN 0 ELSE 1 END,
            p.question_grading_profile_id DESC
        LIMIT 1
    ) profile ON TRUE
    WHERE geq_inner.question_grading_profile_id IS NULL
) sub
WHERE geq.generated_exam_question_id = sub.generated_exam_question_id;

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_question_original_question
    ON delivery.generated_exam_question (original_question_id);

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_question_source_exam_question
    ON delivery.generated_exam_question (source_exam_question_id)
    WHERE source_exam_question_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_question_display_order
    ON delivery.generated_exam_question (
        generated_exam_instance_id,
        canonical_section_order,
        canonical_question_order,
        display_question_order,
        generated_exam_question_id
    );

CREATE INDEX IF NOT EXISTS idx_delivery_generated_exam_question_grading_profile
    ON delivery.generated_exam_question (question_grading_profile_id)
    WHERE question_grading_profile_id IS NOT NULL;

COMMENT ON COLUMN delivery.generated_exam_question.original_question_id IS
    'Stable authored-question link for generated questions. MVQ-1 backfills from question_template_id until a richer authored source model is introduced.';

COMMENT ON COLUMN delivery.generated_exam_question.source_exam_question_id IS
    'Reserved for a future exam-version-scoped authored question identifier. MVQ-1 leaves this nullable when no separate source row exists.';

COMMENT ON COLUMN delivery.generated_exam_question.display_question_order IS
    'Student-facing display order. Legacy question_order remains as backward-compatible storage and fallback.';

COMMENT ON COLUMN delivery.generated_exam_question.canonical_question_order IS
    'Canonical authored ordering used by downstream gradebook/review consumers.';

COMMENT ON COLUMN delivery.generated_exam_question.variant_parameters_json IS
    'Safe generated-question variant metadata snapshot. Student runtime must continue to sanitize any hidden keys or seeds before exposure.';

COMMENT ON COLUMN delivery.generated_exam_question.question_grading_profile_id IS
    'Resolved grading profile snapshot for downstream review and grading fallback safety.';