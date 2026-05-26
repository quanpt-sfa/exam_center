import type { ProcessingStatusResponse as SubmissionProcessingStatusResponse } from '../submissionProcessing/types';

type OpenString<T extends string> = T | (string & {});

export type RuntimeSessionStatus = OpenString<
  | 'CREATED'
  | 'WAITING_FOR_CHECKIN'
  | 'READY_TO_START'
  | 'IN_PROGRESS'
  | 'PAUSED'
  | 'INTERRUPTED'
  | 'COMPLETED'
  | 'CANCELLED'
>;

export type SubmissionStatus = OpenString<
  | 'DRAFT'
  | 'SUBMITTED'
  | 'SEALED'
  | 'GRADED'
  | 'NEEDS_REVIEW'
  | 'PARTIALLY_FAILED'
>;

export type RuntimeStatusSeverity = 'warning' | 'blocker';

export type RuntimeAnswerMode = OpenString<
  | 'TEXT'
  | 'TEXTAREA'
  | 'SQL_TEXT'
  | 'CODE_TEXT'
  | 'JSON'
  | 'FILE_UPLOAD'
  | 'INSTRUCTION_ONLY'
  | 'CAPTURE_ONLY'
  | 'FOUNDATION_ONLY'
  | 'NOT_READY'
  | 'UNSUPPORTED'
  | 'STUDENT_DATABASE'
  | 'EXTERNAL'
>;

export type RuntimeCandidateIdentity = {
  student_id?: number | null;
  full_name: string;
  student_code: string;
  photo_url?: string | null;
  photo_ref?: string | null;
};

export type RuntimeSessionState = {
  exam_session_id: number;
  exam_assignment_id?: number | null;
  exam_sitting_id?: number | null;
  station_assignment_id?: number | null;
  exam_sitting_room_id?: number | null;
  assigned_station_id?: number | null;
  planned_device_id?: number | null;
  station_assignment_status?: string | null;
  assigned_room_id?: number | null;
  session_code?: string | null;
  session_status?: RuntimeSessionStatus | null;
  assignment_status?: string | null;
  sitting_name?: string | null;
  exam_name?: string | null;
  course_code?: string | null;
  course_name?: string | null;
  room_code?: string | null;
  room_name?: string | null;
  station_code?: string | null;
  seat_no?: string | number | null;
  deadline_at?: string | null;
  remaining_seconds?: number | null;
  scheduled_start_at?: string | null;
  scheduled_end_at?: string | null;
  started_at?: string | null;
  submitted_at?: string | null;
  sealed_at?: string | null;
};

export type RuntimeTimer = {
  server_now?: string | null;
  deadline_at?: string | null;
  remaining_seconds?: number | null;
};

export type RuntimeDeviceBindingRequirement = {
  required?: boolean | null;
  can_bind?: boolean | null;
  bind_reason?: string | null;
  station_id?: number | null;
  station_code?: string | null;
  device_id?: number | null;
  asset_tag?: string | null;
  status?: string | null;
  message?: string | null;
  details?: Record<string, unknown> | null;
};

export type RuntimeDeviceBindingSummary = {
  exam_session_id?: number | null;
  station_id?: number | null;
  station_code?: string | null;
  device_id?: number | null;
  device_code?: string | null;
  asset_tag?: string | null;
  binding_status?: string | null;
  bound_at?: string | null;
};

export type RuntimeDeliveryProfileSummary = {
  modality: string;
  runtime_readiness: string;
  delivery_mode?: string | null;
  work_mode?: string | null;
  primary_answer_source?: string | null;
  requires_capture: boolean;
};

export type RuntimeSubmissionCapabilities = {
  can_autosave_text: boolean;
  can_upload_file: boolean;
  can_seal: boolean;
  can_view_processing_status: boolean;
  can_use_database_workspace: boolean;
  can_use_external_capture: boolean;
};

export type RuntimeFileUploadPolicy = {
  allowed_mime_types?: string[] | null;
  allowed_extensions?: string[] | null;
  max_file_size_bytes?: number | null;
};

export type RuntimeResourceBindingSummary = {
  binding_type?: string | null;
  binding_status?: string | null;
  resource_id?: number | null;
  resource_code?: string | null;
  resource_name?: string | null;
  details?: Record<string, unknown> | null;
};

export type QuestionFileMetadata = {
  file_asset_id: number;
  original_filename: string;
  mime_type: string;
  file_size_bytes: number;
  sha256_hash: string;
  uploaded_at?: string | null;
  status?: string | null;
};

export type RuntimeAnswerUi = RuntimeFileUploadPolicy & {
  ui_mode?: string | null;
  input_source?: string | null;
  answer_format?: string | null;
  required?: boolean | null;
  current_file?: QuestionFileMetadata | null;
};

export type QuestionResponseProfile = RuntimeFileUploadPolicy & {
  ui_mode?: string | null;
  input_source?: string | null;
  answer_format?: string | null;
  required?: boolean | null;
  external_work_required?: boolean | null;
  capture_required?: boolean | null;
};

export type StudentGradingProfile = {
  input_source?: string | null;
  answer_language?: string | null;
  grading_engine_code?: string | null;
  comparison_method?: string | null;
  manual_review_policy?: string | null;
  max_score?: number | null;
};

export type QuestionCaptureProfile = {
  requires_capture?: boolean | null;
  required_capture_type?: string | null;
};

export type RuntimeQuestion = {
  generated_exam_question_id: number;
  question_order: number;
  question_code?: string | null;
  question_type: string;
  rendered_question_text: string;
  rendered_question_payload_json?: Record<string, unknown> | null;
  score: number;
  answer_ui?: RuntimeAnswerUi | null;
  response_profile?: QuestionResponseProfile | null;
  student_grading_profile?: StudentGradingProfile | null;
  capture_profile?: QuestionCaptureProfile | null;
};

export type RuntimeBlocker = {
  code: string;
  message: string;
  severity: RuntimeStatusSeverity;
  generated_exam_question_id?: number | null;
  details?: Record<string, unknown> | null;
};

export type RuntimeWarning = RuntimeBlocker;

export type RuntimeContractMetadata = {
  contract_name?: string | null;
  contract_version?: string | null;
  runtime_readiness?: string | null;
  modality?: string | null;
  answer_key_policy?: string | null;
  rendering_source?: string | null;
};

export type RuntimeSubmissionState = {
  exam_submission_id: number;
  exam_session_id: number;
  generated_exam_instance_id?: number | null;
  submission_status?: SubmissionStatus | null;
  opened_at?: string | null;
  submitted_at?: string | null;
  sealed_at?: string | null;
};

export type RuntimePaper = {
  exam_session_id: number;
  generated_exam_instance_id: number;
  generation_status?: string | null;
  questions: RuntimeQuestion[];
};

export type ExamRuntimePayload = {
  session: RuntimeSessionState;
  candidate?: RuntimeCandidateIdentity | null;
  submission: RuntimeSubmissionState;
  paper: RuntimePaper;
  timer?: RuntimeTimer | null;
  runtime_contract?: RuntimeContractMetadata | null;
  device_binding_requirement?: RuntimeDeviceBindingRequirement | null;
  device_binding?: RuntimeDeviceBindingSummary | null;
  delivery_profile?: RuntimeDeliveryProfileSummary | null;
  submission_capabilities?: RuntimeSubmissionCapabilities | null;
  resource_bindings?: RuntimeResourceBindingSummary[] | null;
  blockers?: RuntimeBlocker[] | null;
  warnings?: RuntimeWarning[] | null;
  client_revision: number;
};

export type StudentExamSession = {
  exam_session_id: number;
  exam_assignment_id?: number;
  exam_sitting_id?: number;
  session_code?: string | null;
  session_status?: RuntimeSessionStatus | null;
  assignment_status?: string | null;
  sitting_name?: string | null;
  exam_name?: string | null;
  course_code?: string | null;
  course_name?: string | null;
  room_code?: string | null;
  room_name?: string | null;
  station_code?: string | null;
  seat_no?: string | number | null;
  exam_submission_id?: number | null;
  submission_status?: SubmissionStatus | null;
  scheduled_start_at?: string | null;
  scheduled_end_at?: string | null;
  started_at?: string | null;
  deadline_at?: string | null;
  submitted_at?: string | null;
  sealed_at?: string | null;
};

export type AnswerAutosaveItem = {
  generated_exam_question_id: number;
  answer_type: string;
  answer_text?: string | null;
  answer_payload_json?: Record<string, unknown> | null;
  answer_hash?: string | null;
  answer_length?: number | null;
  client_revision?: number | null;
  metadata_json?: Record<string, unknown> | null;
};

export type AnswerAutosaveRequest = {
  idempotency_key: string;
  client_sequence_no?: number | null;
  client_saved_at?: string | null;
  client_revision: number;
  device_id?: number | null;
  station_id?: number | null;
  metadata_json?: Record<string, unknown> | null;
  answers: AnswerAutosaveItem[];
};

export type AnswerAutosaveResponse = {
  exam_submission_id: number;
  batch_status: string;
  idempotent: boolean;
  server_ack_revision: number;
  items?: Array<Record<string, unknown>>;
};

export type AnswerStateItem = {
  answer_state_id: number;
  generated_exam_question_id: number;
  answer_type?: string | null;
  answer_text?: string | null;
  answer_payload_json?: Record<string, unknown> | null;
  client_version?: number | null;
  server_version?: number | null;
};

export type AnswerStateResponse = {
  exam_submission_id: number;
  server_ack_revision: number;
  items: AnswerStateItem[];
};

export type AnswerFileDescriptor = {
  file_asset_id: number;
  file_name: string;
  mime_type: string;
  file_size_bytes: number;
  sha256: string;
  status: string;
  uploaded_at?: string | null;
};

export type AnswerFileUploadResponse = {
  submission_id: number;
  generated_exam_question_id: number;
  answer_file: AnswerFileDescriptor;
};

export type AnswerFileMetadataResponse = {
  submission_id?: number;
  exam_submission_id?: number;
  generated_exam_question_id: number;
  answer_file: AnswerFileDescriptor;
};

export type AnswerFileSupersedeResponse = {
  submission_id?: number;
  exam_submission_id?: number;
  generated_exam_question_id: number;
  status?: string | null;
  superseded?: boolean | null;
  answer_file?: AnswerFileDescriptor | null;
};

export type SealPreflightBlocker = {
  code: string;
  message: string;
  severity: string;
  generated_exam_question_id?: number | null;
  details?: Record<string, unknown> | null;
};

export type SealPreflightWarning = SealPreflightBlocker;

export type SealPreflightResponse = {
  exam_submission_id: number;
  can_seal: boolean;
  modality: string;
  runtime_readiness: string;
  supported_answer_modes: string[];
  counts: Record<string, unknown>;
  blockers: SealPreflightBlocker[];
  warnings: SealPreflightWarning[];
  generated_at: string;
};

export type SealRequest = {
  reason?: string;
  seal_idempotency_key?: string;
  idempotency_key?: string;
  metadata_json?: Record<string, unknown> | null;
};

export type SealResponse = {
  exam_submission_id: number;
  submission_seal_id: number;
  seal_status: string;
  submission_status: SubmissionStatus;
  idempotent: boolean;
  dispatch_ready?: boolean;
  dispatch_blockers?: string[];
};

export type SubmissionSealStatusResponse = SealResponse;

export type ProcessingStatusResponse = SubmissionProcessingStatusResponse;

export type ExamSessionPaperAsset = {
  paper_asset_id: number;
  asset_kind?: string | null;
  original_filename?: string | null;
  mime_type?: string | null;
  file_size_bytes?: number | null;
  sha256_hash?: string | null;
  page_count?: number | null;
  render_status?: string | null;
  is_active?: boolean | null;
  content_url?: string | null;
};

export type ExamSessionPaperAssetListResponse = {
  exam_session_id: number;
  items: ExamSessionPaperAsset[];
};

export type ExamTakingApiErrorPayload = {
  code: string;
  message: string;
  details?: unknown;
  request_id?: string;
  status?: number;
};

export class ExamTakingApiError extends Error {
  code: string;
  details?: unknown;
  request_id?: string;
  status?: number;

  constructor(payload: ExamTakingApiErrorPayload) {
    super(payload.message);
    this.name = 'ExamTakingApiError';
    this.code = payload.code;
    this.details = payload.details;
    this.request_id = payload.request_id;
    this.status = payload.status;
  }
}

const EDITABLE_TEXT_MODES = new Set<RuntimeAnswerMode>(['TEXT', 'TEXTAREA', 'SQL_TEXT', 'CODE_TEXT', 'JSON']);
const FILE_UPLOAD_MODES = new Set<RuntimeAnswerMode>(['FILE_UPLOAD']);
const NON_EDITABLE_MODES = new Set<RuntimeAnswerMode>([
  'INSTRUCTION_ONLY',
  'CAPTURE_ONLY',
  'FOUNDATION_ONLY',
  'NOT_READY',
  'UNSUPPORTED',
  'STUDENT_DATABASE',
  'EXTERNAL',
]);

export function normalizeAnswerMode(rawMode: string | null | undefined): RuntimeAnswerMode {
  const normalized = String(rawMode || '').trim().toUpperCase();
  if (!normalized) return 'UNSUPPORTED';
  if (normalized === 'TEXT' || normalized === 'TEXTAREA') return normalized;
  if (normalized === 'SQL_TEXT' || normalized === 'SQL' || normalized === 'TEXTBOX_SQL') return 'SQL_TEXT';
  if (normalized === 'CODE_TEXT' || normalized === 'CODE' || normalized === 'CODE_EDITOR') return 'CODE_TEXT';
  if (normalized === 'JSON' || normalized === 'JSON_EDITOR') return 'JSON';
  if (normalized === 'FILE_UPLOAD' || normalized === 'SEALED_FILE_REF') return 'FILE_UPLOAD';
  if (normalized === 'INSTRUCTION_ONLY' || normalized === 'MANUAL_RESPONSE') return 'INSTRUCTION_ONLY';
  if (normalized === 'CAPTURE_ONLY') return 'CAPTURE_ONLY';
  if (normalized === 'FOUNDATION_ONLY') return 'FOUNDATION_ONLY';
  if (normalized === 'NOT_READY') return 'NOT_READY';
  if (normalized === 'UNSUPPORTED') return 'UNSUPPORTED';
  if (normalized === 'STUDENT_DATABASE' || normalized === 'DATABASE') return 'STUDENT_DATABASE';
  if (normalized === 'EXTERNAL' || normalized === 'EXTERNAL_CAPTURE') return 'EXTERNAL';
  return 'UNSUPPORTED';
}

export function isEditableTextMode(mode: RuntimeAnswerMode | string | null | undefined): boolean {
  return EDITABLE_TEXT_MODES.has(normalizeAnswerMode(mode));
}

export function isFileUploadMode(mode: RuntimeAnswerMode | string | null | undefined): boolean {
  return FILE_UPLOAD_MODES.has(normalizeAnswerMode(mode));
}

export function isUnsupportedAnswerMode(mode: RuntimeAnswerMode | string | null | undefined): boolean {
  const normalized = normalizeAnswerMode(mode);
  return NON_EDITABLE_MODES.has(normalized) || (!isEditableTextMode(normalized) && !isFileUploadMode(normalized));
}
