-- Decouples exam authoring from class sections by allowing class_section_id to be NULL.
-- Existing foreign keys and indexes remain valid and are not dropped.

ALTER TABLE assessment.exam ALTER COLUMN class_section_id DROP NOT NULL;
