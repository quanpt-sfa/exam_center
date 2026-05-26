export type ExamSetupRow = Record<string, unknown>;

export type ApiListResponse<T> = {
  items: T[];
  pagination?: Record<string, unknown>;
};

export type ModuleStatus = {
  module: string;
  status: string;
  ready?: boolean;
  endpoint: string;
  error?: string;
};

export type Exam = {
  exam_id: number;
  exam_code?: string | null;
  exam_name?: string | null;
  class_section_id?: number | null;
  assessment_type_id?: number | null;
  description?: string | null;
  exam_status?: string | null;
  status?: string | null;
};

export type ExamVersion = {
  exam_version_id: number;
  exam_id?: number | null;
  exam_code?: string | null;
  version_no?: number | null;
  version_label?: string | null;
  duration_seconds?: number | null;
  total_score?: number | null;
  randomization_mode?: string | null;
  status?: string | null;
};

export type ExamAuthoringBaseData = {
  exams: ExamSetupRow[];
  classSections: ExamSetupRow[];
  assessmentTypes: ExamSetupRow[];
};

export type DeliverySetupBaseData = {
  exams: ExamSetupRow[];
  classSections: ExamSetupRow[];
  rooms: ExamSetupRow[];
  stations: ExamSetupRow[];
  students: ExamSetupRow[];
  instructors: ExamSetupRow[];
  modules: ModuleStatus[];
};

export type ExamSetupBaseData = {
  exams: ExamSetupRow[];
  classSections: ExamSetupRow[];
  assessmentTypes: ExamSetupRow[];
  rooms: ExamSetupRow[];
  stations: ExamSetupRow[];
  students: ExamSetupRow[];
  instructors: ExamSetupRow[];
  modules: ModuleStatus[];
};

export type ExamCreatePayload = {
  exam_code: string;
  exam_name: string;
  class_section_id?: number | null;
  assessment_type_id: number;
  description: string | null;
  exam_status: string;
};

export type ExamUpdatePayload = Partial<ExamCreatePayload>;

export type ExamVersionCreatePayload = {
  version_label: string | null;
  duration_seconds: number;
  total_score: number;
  shuffle_questions: boolean;
  shuffle_options: boolean;
  randomization_mode: string;
  status: string;
};

export type ExamVersionUpdatePayload = Partial<ExamVersionCreatePayload>;

export type ExamVersionPaperAsset = {
  paper_asset_id: number;
  exam_version_id: number;
  asset_kind: string;
  original_filename: string;
  mime_type: string;
  file_size_bytes: number;
  sha256_hash?: string | null;
  page_count?: number | null;
  render_status: string;
  is_active: boolean;
  created_at: string;
  retired_at?: string | null;
};

export type ExamVersionDeliveryProfile = {
  exam_version_delivery_profile_id: number;
  exam_version_id: number;
  delivery_mode: string;
  work_mode: string;
  primary_answer_source: string;
  requires_capture: boolean;
  capture_timing: string;
  default_capture_profile_id: number | null;
  default_grading_engine_id: number | null;
  allow_mixed_question_sources: boolean;
  form_autosave_enabled: boolean;
  database_work_mode: string;
  status: string;
  metadata_json?: Record<string, unknown>;
};

export type DeliveryProfileUpsertPayload = {
  delivery_mode: string;
  work_mode: string;
  primary_answer_source: string;
  requires_capture: boolean;
  capture_timing: string;
  default_capture_profile_id?: number | null;
  default_grading_engine_id?: number | null;
  allow_mixed_question_sources: boolean;
  form_autosave_enabled: boolean;
  database_work_mode: string;
  status: string;
  metadata_json?: Record<string, unknown>;
};

export type QuestionGradingProfileSummary = {
  question_grading_profile_id: number;
  question_template_id: number;
  exam_version_id: number | null;
  input_source: string;
  answer_language: string;
  requires_capture: boolean;
  required_capture_type: string | null;
  capture_profile_code?: string | null;
  grading_engine_code?: string | null;
  comparison_method: string;
  status: string;
  max_score?: number | null;
};

export type QuestionGradingProfileCreatePayload = {
  question_template_id: number;
  input_source: string;
  answer_language: string;
  requires_capture: boolean;
  required_capture_type?: string | null;
  capture_profile_id?: number | null;
  grading_engine_id?: number | null;
  grading_engine_code?: string;
  comparison_method: string;
  status: string;
  metadata_json?: Record<string, unknown>;
};

export type QuestionGradingProfilePatchPayload = {
  input_source?: string;
  answer_language?: string;
  requires_capture?: boolean;
  required_capture_type?: string | null;
  capture_profile_id?: number | null;
  grading_engine_id?: number | null;
  grading_engine_code?: string;
  comparison_method?: string;
  status?: string;
  metadata_json?: Record<string, unknown>;
};

export type FileUploadPlaceholderQuestionPayload = {
  question_label: string;
  question_text: string;
  max_score: number;
  required: boolean;
  allowed_extensions: string[];
  allowed_mime_types: string[];
  max_file_size_bytes: number;
};

export type AtomicFileUploadManualGradingConfigResponse = {
  exam_version_id: number;
  delivery_profile: ExamVersionDeliveryProfile;
  question_template: Record<string, unknown>;
  question_grading_profile: QuestionGradingProfileSummary & { metadata_json?: Record<string, unknown> };
  created_placeholder_question: boolean;
  created_grading_profile: boolean;
  updated_delivery_profile: boolean;
  ready_for_file_upload_runtime: boolean;
};

export type ExamVersionQuestionAuthoringItem = {
  question_template_id: number;
  question_grading_profile_id?: number;
  question_no: number;
  question_title: string;
  prompt_text: string;
  question_type: string;
  response_mode: string;
  render_component: string;
  input_source: string;
  grading_engine_code: string;
  comparison_method: string;
  max_score: number;
  status: string;
  required: boolean;
  mcq_options: string[];
  has_expected_answer: boolean;
};

export type ExamVersionQuestionAuthoringSummary = {
  items: ExamVersionQuestionAuthoringItem[];
  readiness_summary: {
    ready: boolean;
    missing_items: Array<Record<string, unknown>>;
  };
};

export type ExpectedAnswerMetadataSummary = Record<string, unknown>;

export type ExamVersionQuestionAuthoringUpsertPayload = {
  question_no: number;
  question_title: string;
  prompt_text: string;
  question_type: 'TEXTAREA' | 'TEXTBOX_SQL' | 'FILE_UPLOAD' | 'MCQ_SINGLE';
  response_mode?: string;
  render_component?: string;
  max_score: number;
  grading_engine_code?: string;
  comparison_method?: string;
  expected_answer_text?: string;
  expected_answer_json?: Record<string, unknown>;
  status: string;
  required: boolean;
  mcq_options?: string[];
};

export type ExamSitting = {
  exam_sitting_id: number;
  exam_version_id?: number | null;
  exam_version_label?: string | null;
  exam_version_status?: string | null;
  exam_id?: number | null;
  exam_code?: string | null;
  exam_name?: string | null;
  sitting_code: string;
  sitting_name: string;
  scheduled_start_at: string;
  scheduled_end_at: string;
  sitting_status: string;
  warnings?: Array<Record<string, unknown>>;
};

export type SetupSitting = ExamSitting;

export type SetupSittingCreatePayload = {
  sitting_code: string;
  sitting_name: string;
  exam_version_id: number;
  scheduled_start_at: string;
  scheduled_end_at: string;
  status: string;
};

export type SetupSittingUpdatePayload = {
  sitting_name?: string;
  scheduled_start_at?: string;
  scheduled_end_at?: string;
  timezone?: string | null;
};

export type SittingExamVersionPayload = {
  exam_version_id: number;
};

export type DeliverySittingRoom = {
  exam_sitting_room_id: number;
  exam_sitting_id: number;
  room_id: number;
  room_code?: string | null;
  room_name?: string | null;
  capacity?: number | null;
  capacity_allocated?: number | null;
  room_status: string;
};

export type DeliverySittingRoomCreatePayload = {
  room_id: number;
  capacity_allocated?: number | null;
  room_status: string;
};

export type DeliverySittingRoomUpdatePayload = {
  capacity_allocated?: number | null;
  room_status?: string;
};

export type DeliveryProctorAssignment = {
  proctor_assignment_id: number;
  exam_sitting_room_id: number;
  proctor_user_id: number;
  proctor_role: string;
  status: string;
  proctor_display_name?: string | null;
};

export type DeliveryProctorCreatePayload = {
  proctor_user_id: number;
  proctor_role: string;
  status: string;
};

export type DeliveryProctorUpdatePayload = {
  proctor_role?: string;
  status?: string;
};

export type DeliveryExamAssignment = {
  exam_assignment_id: number;
  exam_sitting_id: number;
  student_id: number;
  student_code?: string | null;
  student_name?: string | null;
  assignment_status: string;
  note?: string | null;
};

export type DeliveryExamAssignmentCreatePayload = {
  student_id: number;
  assignment_status: string;
  note?: string | null;
};

export type DeliveryExamAssignmentUpdatePayload = {
  assignment_status?: string;
  note?: string | null;
};

export type DeliveryExamAssignmentCodeImportPayload = {
  assignment_status: string;
  items: Array<{
    sitting_code: string;
    student_code: string;
    note?: string | null;
  }>;
};

export type DeliveryExamAssignmentCodeImportResult = {
  created: DeliveryExamAssignment[];
  errors: Array<Record<string, unknown>>;
  created_count: number;
  error_count: number;
};

export type DeliveryStationAssignment = {
  station_assignment_id: number;
  exam_assignment_id: number;
  exam_sitting_room_id: number;
  station_id: number;
  station_code?: string | null;
  planned_device_id?: number | null;
  planned_device_asset_tag?: string | null;
  status: string;
  student_code?: string | null;
  student_name?: string | null;
  warnings?: string[] | null;
};

export type DeliveryStationAssignmentCreatePayload = {
  exam_sitting_room_id: number;
  station_id: number;
  planned_device_id?: number | null;
  status: string;
};

export type DeliveryStationAssignmentUpdatePayload = {
  station_id?: number;
  planned_device_id?: number | null;
  status?: string;
};

export type ExamSittingPrepareResult = {
  prepared: boolean;
  exam_sitting_id: number;
  exam_version_id: number;
  assignment_count: number;
  question_count: number;
  created_session_count: number;
  reused_session_count: number;
  created_instance_count: number;
  reused_instance_count: number;
  created_generated_question_count: number;
};

export type SittingReadinessIssue = {
  code: string;
  message: string;
  severity?: string;
  status?: string;
  details?: Record<string, unknown>;
};

export type SittingReadiness = {
  exam_sitting_id: number;
  exam_version_id?: number | null;
  sitting_status?: string | null;
  randomization_mode?: string | null;
  shuffle_questions?: boolean;
  shuffle_options?: boolean;
  prepare_strategy?: string | null;
  summary?: string | null;
  can_prepare?: boolean | null;
  can_open?: boolean | null;
  created_session_count?: number | null;
  reused_session_count?: number | null;
  created_generated_question_count?: number | null;
  missing_items?: SittingReadinessIssue[];
  blocking_errors?: SittingReadinessIssue[];
  ready: boolean;
  blockers: SittingReadinessIssue[];
  warnings: SittingReadinessIssue[];
  counts: {
    assignment_count: number;
    room_count: number;
    station_assignment_count: number;
    proctor_count: number;
    question_source_count: number;
    paper_asset_count: number;
  };
};

export type SittingClassSection = {
  exam_sitting_class_section_id: number;
  exam_sitting_id: number;
  class_section_id: number;
  status: string;
  class_code: string;
  class_name: string;
  created_by?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type SittingClassSectionsUpdatePayload = {
  class_section_ids: number[];
};