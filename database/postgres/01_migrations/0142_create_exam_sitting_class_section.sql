-- Join table for associating exam sittings with multiple class sections (delivery planning metadata)
CREATE TABLE IF NOT EXISTS delivery.exam_sitting_class_section (
    exam_sitting_class_section_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_sitting_id bigint NOT NULL,
    class_section_id bigint NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT ck_delivery_exam_sitting_class_section_status CHECK (status IN ('ACTIVE', 'INACTIVE')),
    CONSTRAINT ck_delivery_exam_sitting_class_section_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at),
    CONSTRAINT fk_delivery_exam_sitting_class_section_sitting FOREIGN KEY (exam_sitting_id)
        REFERENCES delivery.exam_sitting (exam_sitting_id) ON DELETE CASCADE,
    CONSTRAINT fk_delivery_exam_sitting_class_section_class FOREIGN KEY (class_section_id)
        REFERENCES academic.class_section (class_section_id) ON DELETE CASCADE,
    CONSTRAINT fk_delivery_exam_sitting_class_section_creator FOREIGN KEY (created_by)
        REFERENCES identity.app_user (user_id),
    CONSTRAINT uq_delivery_exam_sitting_class_section UNIQUE (exam_sitting_id, class_section_id)
);

-- Grant privileges
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE delivery.exam_sitting_class_section TO exam_sys_app;
GRANT SELECT ON TABLE delivery.exam_sitting_class_section TO exam_sys_readonly;
