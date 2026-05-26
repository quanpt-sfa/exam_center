-- Phase 2.1 source: docs/phase_2_assessment_generator_pipeline.md
-- Creates assessment schema for design-time exam objects.

CREATE SCHEMA IF NOT EXISTS assessment;

COMMENT ON SCHEMA assessment IS 'Assessment design-time schema: assessment type, exam, and exam version metadata.';

ALTER SCHEMA assessment OWNER TO exam_sys_owner;

GRANT USAGE ON SCHEMA assessment TO exam_sys_app;
GRANT USAGE ON SCHEMA assessment TO exam_sys_readonly;
GRANT CREATE ON SCHEMA assessment TO exam_sys_owner;