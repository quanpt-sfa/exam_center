import { type FormEvent, type ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import {
  createExam,
  createExamVersion,
  configureFileUploadManualGrading,
  createFileUploadPlaceholderQuestion,
  createExamVersionQuestion,
  loadExamAuthoringBaseData,
  loadExamVersionDeliveryProfile,
  loadExamVersionPaperAssets,
  loadExamVersionQuestions,
  loadExamVersionQuestionGradingProfiles,
  patchQuestionGradingProfile,
  retireExamVersionPaperAsset,
  retireQuestionGradingProfile,
  validateExamVersion,
  upsertExamVersionDeliveryProfile,
  updateExamVersionQuestion,
  updateExam,
  updateExamVersion,
  loadExamVersions as fetchExamVersions,
  publishExamVersion,
  uploadExamVersionPaperAsset,
} from './api/examAuthoringApi';
import {
  assignExamStation,
  assignSittingExamVersion,
  cancelRoomProctor,
  cancelSittingRoom,
  changeExamSittingStatus,
  createDeliverySitting,
  createExamAssignment,
  createRoomProctor,
  createSittingRoom,
  getExamSittingReadiness,
  importAssignmentsFromClassSections,
  importExamAssignmentsByCode,
  listDeliverySittings,
  listExamAssignments,
  listRoomProctors,
  listSeatingPlan,
  listSittingClassSections,
  listSittingRooms,
  listSetupSittings,
  loadDeliverySetupBaseData,
  loadRoomStations,
  prepareExamSittingRuntime,
  updateDeliverySitting,
  updateExamAssignment,
  updateExamStationAssignment,
  updateRoomProctor,
  updateSittingClassSections,
  updateSittingRoom,
} from './api/deliverySetupApi';
import type {
  DeliveryExamAssignment,
  DeliveryProctorAssignment,
  DeliverySittingRoom,
  DeliveryStationAssignment,
  ExamSetupBaseData,
  ExamVersionQuestionAuthoringItem,
  ExamVersionDeliveryProfile,
  ExamVersionPaperAsset,
  ExamSetupRow,
  ModuleStatus,
  QuestionGradingProfileSummary,
  SittingClassSection,
  SittingClassSectionsUpdatePayload,
  SittingReadiness,
  SetupSitting,
} from './api/contracts';
import { CompactPage } from '../../shared/components/compact/CompactPage';
import { ApiStatusChip } from '../../shared/components/compact/ApiStatusChip';
import { CompactPageHeader } from '../../shared/components/compact/CompactPageHeader';
import { CompactStatBar } from '../../shared/components/compact/CompactStatBar';
import { CompactSurface } from '../../shared/components/compact/CompactSurface';
import { CompactToolbar } from '../../shared/components/compact/CompactToolbar';
import { IconActionButton } from '../../shared/components/compact/IconActionButton';
import { isUiApiDiagnosticsEnabled } from '../../shared/uiDiagnostics';

export type SetupSectionKey =
  | 'overview'
  | 'blueprint'
  | 'exam-version'
  | 'delivery-type'
  | 'paper'
  | 'questions'
  | 'response-profile'
  | 'grading-profile'
  | 'expected-answer'
  | 'version-readiness'
  | 'sittings'
  | 'sitting-version'
  | 'sitting-class-sections'
  | 'assignments'
  | 'rooms'
  | 'seating'
  | 'proctors'
  | 'readiness'
  | 'publish';

type SetupSection = {
  key: SetupSectionKey;
  title: string;
  description: string;
  apiStatus: 'connected' | 'partial' | 'missing';
};

type ApiSnapshot = {
  exams: ExamSetupRow[];
  examVersions: ExamSetupRow[];
  classSections: ExamSetupRow[];
  assessmentTypes: ExamSetupRow[];
  rooms: ExamSetupRow[];
  stations: ExamSetupRow[];
  students: ExamSetupRow[];
  instructors: ExamSetupRow[];
  modules: ModuleStatus[];
  loading: boolean;
  error: string | null;
};

const emptyExamSetupBaseData: ExamSetupBaseData = {
  exams: [],
  classSections: [],
  assessmentTypes: [],
  rooms: [],
  stations: [],
  students: [],
  instructors: [],
  modules: [],
};

type ExamForm = {
  exam_code: string;
  exam_name: string;
  class_section_id: string;
  assessment_type_id: string;
  description: string;
  exam_status: string;
};

type VersionForm = {
  version_label: string;
  duration_minutes: string;
  total_score: string;
  randomization_mode: string;
  status: string;
};

type SittingForm = {
  sitting_code: string;
  sitting_name: string;
  exam_version_id: string;
  scheduled_start_at: string;
  scheduled_end_at: string;
  status: string;
};

type SittingRoomForm = {
  room_id: string;
  capacity_allocated: string;
  room_status: string;
};

type ProctorForm = {
  exam_sitting_room_id: string;
  proctor_user_id: string;
  proctor_role: string;
  status: string;
};

type AssignmentForm = {
  student_id: string;
  assignment_status: string;
  note: string;
};

type AssignmentImportForm = {
  rows_text: string;
  assignment_status: string;
  note: string;
};

type StationAssignmentForm = {
  exam_assignment_id: string;
  exam_sitting_room_id: string;
  station_id: string;
  planned_device_id: string;
  status: string;
};

type VersionQuestionForm = {
  question_template_id: string;
  question_no: string;
  question_title: string;
  prompt_text: string;
  question_type: 'TEXTAREA' | 'TEXTBOX_SQL' | 'FILE_UPLOAD' | 'MCQ_SINGLE';
  response_mode: string;
  render_component: string;
  max_score: string;
  grading_engine_code: string;
  comparison_method: string;
  expected_answer_text: string;
  status: string;
  required: boolean;
  mcq_options_text: string;
};

type DeliveryContentType =
  | 'FORM_QUESTION_BASED'
  | 'VISUAL_PAPER_BASED'
  | 'FILE_SUBMISSION_BASED'
  | 'EXTERNAL_APP_BASED'
  | 'DATABASE_TASK_BASED'
  | 'MIXED';

type QuestionDraftSaveResult = {
  ok: boolean;
  message?: string;
  error?: string;
};

type PublishValidationBlocker = {
  code: string;
  message: string;
  severity: string | null;
  status: string | null;
  sectionKey: SetupSectionKey | null;
  sectionTitle: string | null;
};

const setupSections: SetupSection[] = [
  {
    key: 'overview',
    title: 'Tổng quan',
    description: 'Tổng quan hai workflow: soạn đề và thiết lập ca thi.',
    apiStatus: 'partial',
  },
  {
    key: 'blueprint',
    title: 'Đề gốc',
    description: 'Tạo hoặc chọn đề gốc/blueprint.',
    apiStatus: 'connected',
  },
  {
    key: 'exam-version',
    title: 'Phiên bản đề',
    description: 'Tạo, chọn và chỉnh sửa phiên bản đề thuộc đề gốc đang chọn.',
    apiStatus: 'connected',
  },
  {
    key: 'delivery-type',
    title: 'Dạng đề',
    description: 'Khai báo dạng delivery/content của phiên bản đề. Paper/PDF chỉ bắt buộc với dạng hiển thị bằng tài liệu.',
    apiStatus: 'connected',
  },
  {
    key: 'paper',
    title: 'Tài liệu đề thi',
    description: 'Upload PDF/ảnh cho phiên bản đề visual-paper. Đây không phải file bài làm sinh viên.',
    apiStatus: 'connected',
  },
  {
    key: 'questions',
    title: 'Câu hỏi',
    description: 'Soạn câu hỏi theo từng câu cho exam version: form trả lời, cách chấm và đáp án mong đợi.',
    apiStatus: 'connected',
  },
  {
    key: 'response-profile',
    title: 'Form làm bài',
    description: 'Cấu hình cách sinh viên trả lời từng câu: MCQ, text, code/SQL, file upload, database task hoặc instruction-only.',
    apiStatus: 'partial',
  },
  {
    key: 'grading-profile',
    title: 'Cấu hình chấm',
    description: 'Cấu hình grading engine, comparison method, điểm tối đa và manual review policy theo câu.',
    apiStatus: 'connected',
  },
  {
    key: 'expected-answer',
    title: 'Đáp án',
    description: 'Quản lý metadata/snapshot đáp án cho phiên bản đề; không bao giờ đưa đáp án vào API sinh viên.',
    apiStatus: 'connected',
  },
  {
    key: 'version-readiness',
    title: 'Độ sẵn sàng phiên bản đề',
    description: 'Kiểm tra độ sẵn sàng cấu hình, không thay thế bước nhập liệu.',
    apiStatus: 'connected',
  },
  {
    key: 'sittings',
    title: 'Ca thi',
    description: 'Tạo, chọn và chỉnh sửa ca thi cụ thể.',
    apiStatus: 'connected',
  },
  {
    key: 'sitting-version',
    title: 'Phiên bản đề áp dụng',
    description: 'Gắn phiên bản đề cho ca thi. Đây là context version duy nhất của workflow thiết lập ca thi.',
    apiStatus: 'connected',
  },
  {
    key: 'sitting-class-sections',
    title: 'Lớp học phần ca thi',
    description: 'Lớp học phần tham gia ca thi — dùng để lập danh sách dự thi, không phải nguồn đăng ký chính thức.',
    apiStatus: 'connected',
  },
  {
    key: 'assignments',
    title: 'Sinh viên dự thi',
    description: 'Danh sách sinh viên được gắn với ca thi đang chọn.',
    apiStatus: 'connected',
  },
  {
    key: 'rooms',
    title: 'Phòng thi',
    description: 'Phòng/lab được gắn với ca thi đang chọn.',
    apiStatus: 'connected',
  },
  {
    key: 'seating',
    title: 'Xếp máy',
    description: 'Gán sinh viên trong ca thi vào station/máy thuộc phòng đã gắn.',
    apiStatus: 'connected',
  },
  {
    key: 'proctors',
    title: 'Giám thị',
    description: 'Gắn giám thị cho phòng thi hoặc ca thi.',
    apiStatus: 'connected',
  },
  {
    key: 'readiness',
    title: 'Kiểm tra độ sẵn sàng',
    description: 'Kiểm tra độ sẵn sàng cấu hình, không thay thế bước nhập liệu.',
    apiStatus: 'partial',
  },
  {
    key: 'publish',
    title: 'Phát hành / Mở ca thi',
    description: 'Chỉ phát hành/mở ca thi sau khi độ sẵn sàng đạt. Chuẩn bị nặng phải do worker thực hiện.',
    apiStatus: 'partial',
  },
];

const authoringSectionKeys: SetupSectionKey[] = [
  'blueprint',
  'exam-version',
  'delivery-type',
  'paper',
  'questions',
  'response-profile',
  'grading-profile',
  'expected-answer',
  'version-readiness',
];

const deliverySectionKeys: SetupSectionKey[] = [
  'sittings',
  'sitting-version',
  'sitting-class-sections',
  'assignments',
  'rooms',
  'seating',
  'proctors',
  'readiness',
  'publish',
];

const sectionGroups: Array<{ heading: string; keys: SetupSectionKey[] }> = [
  { heading: 'Soạn đề', keys: authoringSectionKeys },
  { heading: 'Thiết lập ca thi', keys: deliverySectionKeys },
];

function publishBlockerSectionForCode(code: string): SetupSectionKey | null {
  const normalized = String(code || '').trim().toLowerCase();
  if (!normalized) {
    return null;
  }

  if (
    normalized.includes('delivery_profile') ||
    normalized.includes('modality') ||
    normalized.includes('capture_profile') ||
    normalized.includes('capture_engine') ||
    normalized.includes('capture_required')
  ) {
    return 'delivery-type';
  }

  if (normalized.includes('response_profile')) {
    return 'response-profile';
  }

  if (normalized.includes('paper_asset') || normalized.includes('visual_paper') || normalized.includes('paper')) {
    return 'paper';
  }

  if (normalized.includes('expected_answer')) {
    return 'expected-answer';
  }

  if (
    normalized.includes('grading_engine') ||
    normalized.includes('grading_profile') ||
    normalized.includes('comparison_method') ||
    normalized.includes('scoring')
  ) {
    return 'grading-profile';
  }

  if (normalized.includes('question')) {
    return 'questions';
  }

  if (
    normalized.includes('exam_not_active') ||
    normalized.includes('published_version_conflict') ||
    normalized.includes('exam_status') ||
    normalized.includes('version_status') ||
    normalized.includes('status_transition') ||
    normalized.startsWith('invalid_')
  ) {
    return 'blueprint';
  }

  return null;
}

function normalizePublishBlockers(items: unknown): PublishValidationBlocker[] {
  if (!Array.isArray(items)) {
    return [];
  }

  return items.map((item) => {
    const value = typeof item === 'object' && item !== null ? (item as Record<string, unknown>) : {};
    const code = asString(value.code, 'unknown');
    const sectionKey = publishBlockerSectionForCode(code);
    const sectionTitle = sectionKey ? setupSections.find((section) => section.key === sectionKey)?.title ?? null : null;
    return {
      code,
      message: asString(value.message, code),
      severity: value.severity !== undefined && value.severity !== null ? asString(value.severity) : null,
      status: value.status !== undefined && value.status !== null ? asString(value.status) : null,
      sectionKey,
      sectionTitle,
    };
  });
}

function publishBlockersFromDetails(details: unknown): PublishValidationBlocker[] {
  if (details && typeof details === 'object' && !Array.isArray(details)) {
    const value = details as Record<string, unknown>;
    return normalizePublishBlockers(value.errors);
  }
  return [];
}

const initialSnapshot: ApiSnapshot = {
  exams: [],
  examVersions: [],
  classSections: [],
  assessmentTypes: [],
  rooms: [],
  stations: [],
  students: [],
  instructors: [],
  modules: [],
  loading: true,
  error: null,
};

const initialExamForm: ExamForm = {
  exam_code: '',
  exam_name: '',
  class_section_id: '',
  assessment_type_id: '',
  description: '',
  exam_status: 'DRAFT',
};

const initialVersionForm: VersionForm = {
  version_label: '',
  duration_minutes: '90',
  total_score: '10',
  randomization_mode: 'FIXED',
  status: 'DRAFT',
};

const initialSittingForm: SittingForm = {
  sitting_code: '',
  sitting_name: '',
  exam_version_id: '',
  scheduled_start_at: '',
  scheduled_end_at: '',
  status: 'DRAFT',
};

const initialSittingRoomForm: SittingRoomForm = {
  room_id: '',
  capacity_allocated: '',
  room_status: 'PLANNED',
};

const initialProctorForm: ProctorForm = {
  exam_sitting_room_id: '',
  proctor_user_id: '',
  proctor_role: 'ROOM_PROCTOR',
  status: 'ASSIGNED',
};

const initialAssignmentForm: AssignmentForm = {
  student_id: '',
  assignment_status: 'ASSIGNED',
  note: '',
};

const initialAssignmentImportForm: AssignmentImportForm = {
  rows_text: '',
  assignment_status: 'ASSIGNED',
  note: '',
};

const initialStationAssignmentForm: StationAssignmentForm = {
  exam_assignment_id: '',
  exam_sitting_room_id: '',
  station_id: '',
  planned_device_id: '',
  status: 'ASSIGNED',
};

const initialVersionQuestionForm: VersionQuestionForm = {
  question_template_id: '',
  question_no: '1',
  question_title: '',
  prompt_text: '',
  question_type: 'TEXTAREA',
  response_mode: 'LONG_TEXT',
  render_component: 'TEXTAREA',
  max_score: '1',
  grading_engine_code: 'MANUAL_RUBRIC',
  comparison_method: 'MANUAL_RUBRIC',
  expected_answer_text: '',
  status: 'ACTIVE',
  required: true,
  mcq_options_text: '',
};

const examActivationBlockedStatuses = new Set(['CLOSED', 'ARCHIVED', 'CANCELLED']);

const questionVersionMissingMessage = 'Vui lòng chọn hoặc tạo phiên bản đề trước.';
const questionVersionStaleMessage = 'Phiên bản đề đã chọn không còn hợp lệ. Vui lòng chọn lại phiên bản đề.';

const deliveryContentTypeOptions: Array<{ label: string; value: DeliveryContentType }> = [
  { value: 'FORM_QUESTION_BASED', label: 'FORM_QUESTION_BASED - Form câu hỏi' },
  { value: 'VISUAL_PAPER_BASED', label: 'VISUAL_PAPER_BASED - Hiển thị PDF/ảnh đề thi' },
  { value: 'FILE_SUBMISSION_BASED', label: 'FILE_SUBMISSION_BASED - Sinh viên nộp file bài làm' },
  { value: 'EXTERNAL_APP_BASED', label: 'EXTERNAL_APP_BASED - Làm trên ứng dụng ngoài' },
  { value: 'DATABASE_TASK_BASED', label: 'DATABASE_TASK_BASED - Bài thực hành database' },
  { value: 'MIXED', label: 'MIXED - Kết hợp nhiều dạng' },
];

function getDeliveryContentType(profile: ExamVersionDeliveryProfile | null): DeliveryContentType | '' {
  if (!profile) {
    return '';
  }
  const metadata = profile.metadata_json ?? {};
  const declared = String(metadata.delivery_content_type ?? metadata.conceptual_delivery_type ?? '').toUpperCase();
  if (deliveryContentTypeOptions.some((option) => option.value === declared)) {
    return declared as DeliveryContentType;
  }

  const deliveryMode = String(profile.delivery_mode ?? '').toUpperCase();
  const primaryAnswerSource = String(profile.primary_answer_source ?? '').toUpperCase();
  if (deliveryMode === 'FORM_BASED' && primaryAnswerSource === 'SEALED_FORM_ANSWER') return 'FORM_QUESTION_BASED';
  if (deliveryMode === 'DATABASE_BASED' || primaryAnswerSource === 'STUDENT_DATABASE') return 'DATABASE_TASK_BASED';
  if (deliveryMode === 'EXTERNAL_SYSTEM_BASED' || primaryAnswerSource === 'AMIS_API') return 'EXTERNAL_APP_BASED';
  if (deliveryMode === 'MIXED' || primaryAnswerSource === 'MIXED') return 'MIXED';
  if (deliveryMode === 'FILE_BASED' && primaryAnswerSource === 'FILE_ARTIFACT') {
    if (metadata.visual_paper_required || metadata.paper_asset_required || metadata.requires_visual_paper) {
      return 'VISUAL_PAPER_BASED';
    }
    return 'FILE_SUBMISSION_BASED';
  }
  return '';
}

function buildDeliveryProfilePayload(contentType: DeliveryContentType, profile: ExamVersionDeliveryProfile | null) {
  const metadata = {
    ...(profile?.metadata_json ?? {}),
    delivery_content_type: contentType,
    conceptual_delivery_type: contentType,
  };
  const base = {
    work_mode: profile?.work_mode || 'INDIVIDUAL',
    requires_capture: false,
    capture_timing: 'NONE',
    default_capture_profile_id: profile?.default_capture_profile_id ?? null,
    default_grading_engine_id: profile?.default_grading_engine_id ?? null,
    allow_mixed_question_sources: false,
    form_autosave_enabled: true,
    database_work_mode: 'NONE',
    status: profile?.status || 'ACTIVE',
  };

  switch (contentType) {
    case 'FORM_QUESTION_BASED':
      return {
        ...base,
        delivery_mode: 'FORM_BASED',
        primary_answer_source: 'SEALED_FORM_ANSWER',
        metadata_json: {
          ...metadata,
          allow_form_answers: true,
          visual_paper_required: false,
          paper_asset_required: false,
          requires_visual_paper: false,
        },
      };
    case 'VISUAL_PAPER_BASED':
      return {
        ...base,
        delivery_mode: 'FILE_BASED',
        primary_answer_source: 'FILE_ARTIFACT',
        form_autosave_enabled: false,
        metadata_json: {
          ...metadata,
          exam_modality: 'VISUAL_PAPER_BASED',
          modality_code: 'VISUAL_PAPER_BASED',
          grading_policy: 'MANUAL_RUBRIC',
          allow_form_answers: false,
          visual_paper_required: true,
          paper_asset_required: true,
          requires_visual_paper: true,
        },
      };
    case 'FILE_SUBMISSION_BASED':
      return {
        ...base,
        delivery_mode: 'FILE_BASED',
        primary_answer_source: 'FILE_ARTIFACT',
        form_autosave_enabled: false,
        metadata_json: {
          ...metadata,
          allow_form_answers: false,
          visual_paper_required: false,
          paper_asset_required: false,
          requires_visual_paper: false,
        },
      };
    case 'EXTERNAL_APP_BASED':
      return {
        ...base,
        delivery_mode: 'EXTERNAL_SYSTEM_BASED',
        primary_answer_source: 'AMIS_API',
        requires_capture: true,
        capture_timing: 'AFTER_SEAL',
        database_work_mode: 'EXTERNAL_SAAS',
        metadata_json: {
          ...metadata,
          allow_form_answers: true,
          visual_paper_required: false,
          paper_asset_required: false,
          requires_visual_paper: false,
        },
      };
    case 'DATABASE_TASK_BASED':
      return {
        ...base,
        delivery_mode: 'DATABASE_BASED',
        primary_answer_source: 'STUDENT_DATABASE',
        requires_capture: true,
        capture_timing: 'AFTER_SEAL',
        database_work_mode: 'SERVER_HOSTED',
        metadata_json: {
          ...metadata,
          allow_form_answers: true,
          visual_paper_required: false,
          paper_asset_required: false,
          requires_visual_paper: false,
        },
      };
    case 'MIXED':
      return {
        ...base,
        delivery_mode: 'MIXED',
        primary_answer_source: 'MIXED',
        allow_mixed_question_sources: true,
        database_work_mode: 'MIXED',
        metadata_json: {
          ...metadata,
          allow_form_answers: true,
          visual_paper_required: false,
          paper_asset_required: false,
          requires_visual_paper: false,
        },
      };
  }
}

function asString(value: unknown, fallback = '-'): string {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  return String(value);
}

function asNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function getExamStatus(row: ExamSetupRow | undefined, fallback = ''): string {
  return asString(row?.exam_status ?? row?.status, fallback).trim().toUpperCase();
}

function buildExamStatusUpdatePayload(exam: ExamSetupRow | undefined, form: ExamForm, examStatus: string) {
  const classSectionId = exam?.class_section_id ?? form.class_section_id;
  const assessmentTypeId = exam?.assessment_type_id ?? form.assessment_type_id;

  return {
    exam_code: asString(exam?.exam_code, form.exam_code).trim(),
    exam_name: asString(exam?.exam_name, form.exam_name).trim(),
    class_section_id: classSectionId === null || classSectionId === undefined || classSectionId === '' ? null : Number(classSectionId),
    assessment_type_id: Number(assessmentTypeId),
    description: asString(exam?.description, form.description).trim() || null,
    exam_status: examStatus,
  };
}

function getId(row: Record<string, unknown>, key: string): string {
  return asString(row[key], '');
}

function getExamVersionId(row: Record<string, unknown>): string {
  return asString(row.exam_version_id ?? row.version_id ?? row.id, '');
}

function formatExamVersionOptionLabel(version: Record<string, unknown>, fallbackId = ''): string {
  const versionLabel = asString(version.version_label, `Version ${asString(version.version_no, fallbackId || '-')}`);
  const examCode = asString(version.exam_code, '').trim();
  const status = asString(version.status ?? version.exam_version_status, '').trim();
  return `${examCode ? `${examCode} - ` : ''}${versionLabel}${status ? ` · ${status}` : ''}`;
}

function assignmentIsActive(assignment: Pick<DeliveryExamAssignment, 'assignment_status'>): boolean {
  return !['CANCELLED', 'VOIDED'].includes(String(assignment.assignment_status || '').toUpperCase());
}

function stationAssignmentIsActive(assignment: Pick<DeliveryStationAssignment, 'status'>): boolean {
  return !['CANCELLED', 'NO_SHOW'].includes(String(assignment.status || '').toUpperCase());
}

function normalizeQuestionErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error ?? '');
  if (/resource not found/i.test(message) || /master_data_not_found/i.test(message)) {
    return questionVersionStaleMessage;
  }
  return message || 'Không tải được danh sách câu hỏi.';
}

function formatMinutes(seconds: unknown): string {
  const value = asNumber(seconds);
  if (!value) {
    return '-';
  }
  return `${Math.round(value / 60)} phút`;
}

function formatFileSize(bytes: unknown): string {
  const value = Number(bytes);
  if (!Number.isFinite(value) || value <= 0) {
    return '-';
  }
  if (value < 1024) {
    return `${Math.round(value)} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(2)} MB`;
}

function formatShaPrefix(value: unknown): string {
  const text = String(value ?? '').trim();
  if (!text) {
    return '-';
  }
  return text.slice(0, 12);
}

function questionTypeDefaults(questionType: VersionQuestionForm['question_type']) {
  if (questionType === 'TEXTBOX_SQL') {
    return {
      response_mode: 'SQL_TEXT',
      render_component: 'SQL_EDITOR',
      grading_engine_code: 'SQL_RESULT_COMPARATOR',
      comparison_method: 'EXACT_RESULT_SET',
    };
  }
  if (questionType === 'FILE_UPLOAD') {
    return {
      response_mode: 'FILE_UPLOAD',
      render_component: 'FILE_UPLOAD_BOX',
      grading_engine_code: 'MANUAL_RUBRIC',
      comparison_method: 'MANUAL_RUBRIC',
    };
  }
  if (questionType === 'MCQ_SINGLE') {
    return {
      response_mode: 'MCQ_SINGLE',
      render_component: 'RADIO_GROUP',
      grading_engine_code: 'MCQ_AUTO_GRADER',
      comparison_method: 'EXACT_RESULT_SET',
    };
  }
  return {
    response_mode: 'LONG_TEXT',
    render_component: 'TEXTAREA',
    grading_engine_code: 'MANUAL_RUBRIC',
    comparison_method: 'MANUAL_RUBRIC',
  };
}

function inputSourceForQuestionType(questionType: VersionQuestionForm['question_type']): string {
  if (questionType === 'FILE_UPLOAD') {
    return 'SEALED_FILE_REF';
  }
  if (questionType === 'MCQ_SINGLE') {
    return 'SEALED_JSON_ANSWER';
  }
  return 'SEALED_TEXT_ANSWER';
}

function requiresExpectedAnswerForQuestion(question: VersionQuestionForm): boolean {
  return question.question_type === 'TEXTBOX_SQL' || question.question_type === 'MCQ_SINGLE';
}

const lockedSittingVersionStatuses = new Set(['READY', 'OPEN', 'IN_PROGRESS', 'CLOSED', 'FINALIZED', 'ARCHIVED']);

function sittingVersionIsLocked(sitting: SetupSitting | undefined): boolean {
  return lockedSittingVersionStatuses.has(String(sitting?.sitting_status || '').trim().toUpperCase());
}

function questionTypeLabel(questionType: VersionQuestionForm['question_type']): string {
  if (questionType === 'TEXTBOX_SQL') {
    return 'TEXTBOX_SQL (nhập SQL)';
  }
  if (questionType === 'MCQ_SINGLE') {
    return 'MCQ_SINGLE (trắc nghiệm 1 đáp án)';
  }
  if (questionType === 'FILE_UPLOAD') {
    return 'FILE_UPLOAD (nộp tệp)';
  }
  return 'TEXTAREA (tự luận)';
}

function questionResponseProfileLabel(question: Pick<VersionQuestionForm, 'question_type' | 'required'>): string {
  const requiredText = question.required ? 'Bắt buộc nhập' : 'Không bắt buộc';
  if (question.question_type === 'TEXTBOX_SQL') {
    return `Ô nhập câu lệnh SQL cho sinh viên. ${requiredText}.`;
  }
  if (question.question_type === 'MCQ_SINGLE') {
    return `Nhóm lựa chọn một đáp án. ${requiredText}.`;
  }
  if (question.question_type === 'FILE_UPLOAD') {
    return `Ô nộp tệp bài làm của sinh viên. ${requiredText}.`;
  }
  return `Ô nhập bài tự luận dạng văn bản dài. ${requiredText}.`;
}

function questionPresetSummary(question: VersionQuestionForm): { response: string; grading: string; expected: string } {
  const inputSource = inputSourceForQuestionType(question.question_type);
  return {
    response: `${question.response_mode || '-'} / ${question.render_component || '-'} / ${inputSource}`,
    grading: `${question.grading_engine_code || '-'} / ${question.comparison_method || '-'}`,
    expected: requiresExpectedAnswerForQuestion(question) ? 'Bắt buộc' : 'Không bắt buộc',
  };
}

const questionPresetIntro = [
  {
    type: 'TEXTAREA',
    response: questionPresetSummary({ ...initialVersionQuestionForm, question_type: 'TEXTAREA', ...questionTypeDefaults('TEXTAREA') }).response,
    grading: questionPresetSummary({ ...initialVersionQuestionForm, question_type: 'TEXTAREA', ...questionTypeDefaults('TEXTAREA') }).grading,
    expected: 'Không bắt buộc',
  },
  {
    type: 'TEXTBOX_SQL',
    response: questionPresetSummary({ ...initialVersionQuestionForm, question_type: 'TEXTBOX_SQL', ...questionTypeDefaults('TEXTBOX_SQL') }).response,
    grading: questionPresetSummary({ ...initialVersionQuestionForm, question_type: 'TEXTBOX_SQL', ...questionTypeDefaults('TEXTBOX_SQL') }).grading,
    expected: 'Bắt buộc',
  },
  {
    type: 'FILE_UPLOAD',
    response: questionPresetSummary({ ...initialVersionQuestionForm, question_type: 'FILE_UPLOAD', ...questionTypeDefaults('FILE_UPLOAD') }).response,
    grading: questionPresetSummary({ ...initialVersionQuestionForm, question_type: 'FILE_UPLOAD', ...questionTypeDefaults('FILE_UPLOAD') }).grading,
    expected: 'Không bắt buộc',
  },
  {
    type: 'MCQ_SINGLE',
    response: questionPresetSummary({ ...initialVersionQuestionForm, question_type: 'MCQ_SINGLE', ...questionTypeDefaults('MCQ_SINGLE') }).response,
    grading: questionPresetSummary({ ...initialVersionQuestionForm, question_type: 'MCQ_SINGLE', ...questionTypeDefaults('MCQ_SINGLE') }).grading,
    expected: 'Bắt buộc',
  },
];

function validateQuestionDraftForUx(
  draft: VersionQuestionForm,
  existingQuestionNos: Set<number>,
  options?: { ignoreQuestionNo?: number }
): string | null {
  const questionNo = Number(draft.question_no);
  if (!Number.isFinite(questionNo) || questionNo <= 0) {
    return 'question_no là bắt buộc và phải lớn hơn 0.';
  }
  if (existingQuestionNos.has(questionNo) && questionNo !== options?.ignoreQuestionNo) {
    return 'question_no bị trùng trong phiên bản đề hiện tại.';
  }
  if (!draft.prompt_text.trim()) {
    return 'prompt_text là bắt buộc.';
  }
  const maxScore = Number(draft.max_score);
  if (!Number.isFinite(maxScore) || maxScore <= 0) {
    return 'max_score phải lớn hơn 0.';
  }
  if (!draft.question_type) {
    return 'question_type là bắt buộc.';
  }
  if (draft.question_type === 'TEXTBOX_SQL' && !draft.expected_answer_text.trim()) {
    return 'TEXTBOX_SQL bắt buộc có expected answer.';
  }
  if (draft.question_type === 'MCQ_SINGLE') {
    const optionsList = draft.mcq_options_text
      .split('\n')
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
    if (!optionsList.length) {
      return 'MCQ_SINGLE bắt buộc có danh sách lựa chọn.';
    }
    const expected = draft.expected_answer_text.trim();
    if (!expected) {
      return 'MCQ_SINGLE bắt buộc có đáp án đúng.';
    }
    const optionKeys = optionsList.map((item) => item.split('.')[0].trim().toUpperCase());
    const normalizedExpected = expected.toUpperCase();
    const matchedCount = optionsList.filter(
      (item) => item.toUpperCase() === normalizedExpected || item.split('.')[0].trim().toUpperCase() === normalizedExpected
    ).length;
    if (matchedCount !== 1 || (!optionKeys.includes(normalizedExpected) && !optionsList.some((item) => item.toUpperCase() === normalizedExpected))) {
      return 'MCQ_SINGLE cần đúng 1 đáp án hợp lệ thuộc danh sách lựa chọn.';
    }
  }
  return null;
}

const stationCodeCollator = new Intl.Collator('vi', { numeric: true, sensitivity: 'base' });

function sortByStationCode<T extends { station_code?: string | null }>(rows: T[]): T[] {
  return [...rows].sort((a, b) => stationCodeCollator.compare(asString(a.station_code, ''), asString(b.station_code, '')));
}

function StatusBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase().replaceAll('_', '-');
  return <span className={`setup-status setup-status-${normalized}`}>{value}</span>;
}

function ApiCoverageBadge({ status }: { status: SetupSection['apiStatus'] }) {
  const label = status === 'connected' ? 'Đã nối API' : status === 'partial' ? 'Nối một phần' : 'Chưa có API';
  return <ApiStatusChip status={status} label={label} />;
}

function ApiCoverageNotice({ children, status }: { children: string; status: SetupSection['apiStatus'] }) {
  if (!isUiApiDiagnosticsEnabled()) {
    return null;
  }

  return (
    <p className="setup-api-diagnostic" role="status" aria-live="polite">
      <ApiCoverageBadge status={status} />
      <span>{children}</span>
    </p>
  );
}

function TextInput({
  id,
  label,
  type = 'text',
  placeholder,
  value,
  onChange,
  required = false,
}: {
  id: string;
  label: string;
  type?: string;
  placeholder?: string;
  value?: string;
  onChange?: (value: string) => void;
  required?: boolean;
}) {
  return (
    <label htmlFor={id}>
      {label}
      <input
        id={id}
        type={type}
        placeholder={placeholder}
        required={required}
        value={value}
        onChange={onChange ? (event) => onChange(event.target.value) : undefined}
      />
    </label>
  );
}

function SelectInput({
  id,
  label,
  options,
  value,
  onChange,
  disabled = false,
  placeholder = 'Vui lòng chọn',
}: {
  id: string;
  label: string;
  options: Array<{ label: string; value: string }>;
  value?: string;
  onChange?: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
}) {
  return (
    <label htmlFor={id}>
      {label}
      <select id={id} value={value} onChange={onChange ? (event) => onChange(event.target.value) : undefined} disabled={disabled}>
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function OverviewPanel({
  snapshot,
  onSelect,
}: {
  snapshot: ApiSnapshot;
  onSelect: (key: SetupSectionKey) => void;
}) {
  const showApiDiagnostics = isUiApiDiagnosticsEnabled();
  const coverageRows = [
    { label: 'Đề thi / exam version', status: 'connected', count: snapshot.examVersions.length || snapshot.exams.length },
    { label: 'Danh mục phòng', status: 'connected', count: snapshot.rooms.length },
    { label: 'Danh mục chỗ ngồi', status: 'connected', count: snapshot.stations.length },
    { label: 'Danh mục sinh viên', status: 'connected', count: snapshot.students.length },
    { label: 'Danh mục giảng viên', status: 'connected', count: snapshot.instructors.length },
    { label: 'Ca thi / phòng trong ca / xếp chỗ / giám thị', status: snapshot.modules.length > 0 ? 'connected' : 'partial', count: snapshot.modules.length },
  ] as const;

  const connectionRows = [
    {
      layer: 'Frontend service',
      detail: 'API client tách theo workflow authoring và delivery.',
      status: 'CONNECTED',
    },
    {
      layer: 'Backend services',
      detail: 'FastAPI route đi qua schema/use_case/service/repository/mapper trước khi tới PostgreSQL.',
      status: 'CONNECTED',
    },
    {
      layer: 'Dịch vụ nền',
      detail: 'Capture/grading/import chạy qua job/status API; trình duyệt không gọi dịch vụ nền trực tiếp.',
      status: 'CONNECTED',
    },
  ];

  return (
    <div className="setup-overview-grid">
      {showApiDiagnostics ? (
        <>
          <section className="setup-card setup-card-wide">
            <div className="section-heading">
              <div>
                <h3>Tình trạng nối API</h3>
                <p className="muted">Những phần có endpoint hiện đã lấy dữ liệu thật từ FastAPI.</p>
              </div>
            </div>
            <div className="setup-checklist">
              {coverageRows.map((item) => (
                <div className="setup-check-row" key={item.label}>
                  <ApiCoverageBadge status={item.status} />
                  <span>{item.label}</span>
                  <strong>{item.count}</strong>
                </div>
              ))}
            </div>
          </section>

          <section className="setup-card setup-card-wide">
            <div className="section-heading">
              <div>
                <h3>Luồng kết nối</h3>
                <p className="muted">Không nối trực tiếp từ giao diện xuống database hoặc tiến trình nền.</p>
              </div>
            </div>
            <SimpleTable
              columns={[
                ['layer', 'Lớp'],
                ['detail', 'Cách nối'],
                ['status', 'Trạng thái'],
              ]}
              rows={connectionRows}
            />
          </section>
        </>
      ) : null}

      {setupSections
        .filter((section) => section.key !== 'overview')
        .map((section, index) => (
          <article className="setup-step-card" key={section.key}>
            <span className="setup-step-number">{index + 1}</span>
            <ApiCoverageBadge status={section.apiStatus} />
            <h3>{section.title}</h3>
            <p>{section.description}</p>
            <button type="button" onClick={() => onSelect(section.key)}>
              Mở bước
            </button>
          </article>
        ))}
    </div>
  );
}

function ExamVersionPanel({
  mode,
  exams,
  classSections,
  assessmentTypes,
  versions,
  selectedExamId,
  selectedExamVersionId,
  examForm,
  examSubmitting,
  examMessage,
  examError,
  versionForm,
  submitting,
  submitMessage,
  submitError,
  versionPublishing,
  versionPublishMessage,
  versionPublishError,
  versionPublishBlockers,
  examActivationLoading,
  onPublishVersion,
  onActivateExamBlueprint,
  onSelect,
  paperAssets,
  paperAssetsLoading,
  paperSubmitting,
  paperMessage,
  paperError,
  deliveryProfile,
  deliveryContentType,
  gradingProfiles,
  profileLoading,
  profileSubmitting,
  profileMessage,
  profileError,
  versionQuestions,
  questionReadiness,
  questionForm,
  questionSubmitting,
  questionMessage,
  questionError,
  onSelectExam,
  onSelectExamVersion,
  onExamFormChange,
  onExamSubmit,
  onFormChange,
  onSubmit,
  onUploadPaperAsset,
  onRetirePaperAsset,
  onDeliveryContentTypeChange,
  onSaveDeliveryContentType,
  onConfigureFileUploadManualGrading,
  onApplyFileUploadPreset,
  onCreatePlaceholderQuestion,
  onRetireGradingProfile,
  onQuestionFormChange,
  onQuestionTypeChange,
  onQuestionSubmit,
  onQuestionSaveDraft,
  onQuestionEdit,
}: {
  mode:
    | 'blueprint'
    | 'exam-version'
    | 'delivery-type'
    | 'paper'
    | 'questions'
    | 'response-profile'
    | 'grading-profile'
    | 'expected-answer'
    | 'version-readiness';
  exams: ExamSetupRow[];
  classSections: ExamSetupRow[];
  assessmentTypes: ExamSetupRow[];
  versions: ExamSetupRow[];
  selectedExamId: string;
  selectedExamVersionId: string;
  examForm: ExamForm;
  examSubmitting: boolean;
  examMessage: string | null;
  examError: string | null;
  versionForm: VersionForm;
  submitting: boolean;
  submitMessage: string | null;
  submitError: string | null;
  versionPublishing: boolean;
  versionPublishMessage: string | null;
  versionPublishError: string | null;
  versionPublishBlockers: PublishValidationBlocker[];
  examActivationLoading: boolean;
  onPublishVersion: () => Promise<void>;
  onActivateExamBlueprint: () => Promise<void>;
  onSelect: (key: SetupSectionKey) => void;
  paperAssets: ExamVersionPaperAsset[];
  paperAssetsLoading: boolean;
  paperSubmitting: boolean;
  paperMessage: string | null;
  paperError: string | null;
  deliveryProfile: ExamVersionDeliveryProfile | null;
  deliveryContentType: DeliveryContentType | '';
  gradingProfiles: QuestionGradingProfileSummary[];
  profileLoading: boolean;
  profileSubmitting: boolean;
  profileMessage: string | null;
  profileError: string | null;
  versionQuestions: ExamVersionQuestionAuthoringItem[];
  questionReadiness: { ready: boolean; missing_items: Array<Record<string, unknown>> };
  questionForm: VersionQuestionForm;
  questionSubmitting: boolean;
  questionMessage: string | null;
  questionError: string | null;
  onSelectExam: (value: string) => void;
  onSelectExamVersion: (value: string) => void;
  onExamFormChange: (patch: Partial<ExamForm>) => void;
  onExamSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onFormChange: (patch: Partial<VersionForm>) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onUploadPaperAsset: (file: File) => Promise<void>;
  onRetirePaperAsset: (paperAssetId: number) => Promise<void>;
  onDeliveryContentTypeChange: (value: DeliveryContentType | '') => void;
  onSaveDeliveryContentType: () => Promise<void>;
  onConfigureFileUploadManualGrading: () => Promise<void>;
  onApplyFileUploadPreset: () => Promise<void>;
  onCreatePlaceholderQuestion: () => Promise<void>;
  onRetireGradingProfile: (questionGradingProfileId: number) => Promise<void>;
  onQuestionFormChange: (patch: Partial<VersionQuestionForm>) => void;
  onQuestionTypeChange: (questionType: VersionQuestionForm['question_type']) => void;
  onQuestionSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onQuestionSaveDraft: (draft: VersionQuestionForm) => Promise<QuestionDraftSaveResult>;
  onQuestionEdit: (item: ExamVersionQuestionAuthoringItem) => void;
}) {
  type QuestionDraftPanel = VersionQuestionForm & {
    panel_id: string;
    is_saved: boolean;
    save_error: string | null;
    save_message: string | null;
    saving: boolean;
  };

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [questionCount, setQuestionCount] = useState('1');
  const [questionPanels, setQuestionPanels] = useState<QuestionDraftPanel[]>([]);
  const [questionPanelError, setQuestionPanelError] = useState<string | null>(null);
  const [showAdvancedQuestionConfig, setShowAdvancedQuestionConfig] = useState(false);
  const questionPanelsVersionRef = useRef<string>('');
  const examOptions = exams.map((exam) => ({
    value: getId(exam, 'exam_id'),
    label: `${asString(exam.exam_code)} - ${asString(exam.exam_name)}`,
  }));
  const classSectionOptions = classSections.map((section) => ({
    value: getId(section, 'class_section_id'),
    label: `${asString(section.class_code)} - ${asString(section.class_name, asString(section.course_name))}`,
  }));
  const assessmentTypeOptions = assessmentTypes.map((type) => ({
    value: getId(type, 'assessment_type_id'),
    label: `${asString(type.type_code)} - ${asString(type.type_name)}`,
  }));
  const versionOptions = versions.map((version) => ({
    value: getId(version, 'exam_version_id'),
    label: `${asString(version.version_label, `Version ${asString(version.version_no)}`)} (${asString(version.status)})`,
  }));
  const hasActiveAsset = paperAssets.some((asset) => Boolean(asset.is_active));
  const selectedVersion = versions.find((version) => getId(version, 'exam_version_id') === selectedExamVersionId);
  const selectedExam = exams.find((exam) => getId(exam, 'exam_id') === selectedExamId);
  const hasSelectedVersion = Boolean(selectedExamVersionId);
  const existingSavedQuestionNos = useMemo(
    () =>
      new Set(
        versionQuestions
          .map((item) => Number(item.question_no))
          .filter((value) => Number.isFinite(value) && value > 0)
      ),
    [versionQuestions]
  );

  function createQuestionPanelDraft(questionNo: number, suggestedScore: string): QuestionDraftPanel {
    return {
      ...initialVersionQuestionForm,
      panel_id: `draft-${questionNo}-${Date.now()}-${Math.round(Math.random() * 100000)}`,
      question_no: String(questionNo),
      question_title: `Câu ${questionNo}`,
      max_score: suggestedScore,
      status: 'ACTIVE',
      is_saved: false,
      save_error: null,
      save_message: null,
      saving: false,
    };
  }

  function fromSavedQuestion(item: ExamVersionQuestionAuthoringItem): QuestionDraftPanel {
    return {
      question_template_id: String(item.question_template_id),
      question_no: String(item.question_no || 1),
      question_title: item.question_title || '',
      prompt_text: item.prompt_text || '',
      question_type: (['TEXTAREA', 'TEXTBOX_SQL', 'FILE_UPLOAD', 'MCQ_SINGLE'].includes(item.question_type)
        ? item.question_type
        : 'TEXTAREA') as VersionQuestionForm['question_type'],
      response_mode: item.response_mode || '',
      render_component: item.render_component || '',
      max_score: String(item.max_score || 1),
      grading_engine_code: item.grading_engine_code || '',
      comparison_method: item.comparison_method || '',
      expected_answer_text: '',
      status: item.status || 'ACTIVE',
      required: item.required !== false,
      mcq_options_text: Array.isArray(item.mcq_options) ? item.mcq_options.join('\n') : '',
      panel_id: `saved-${item.question_template_id}`,
      is_saved: true,
      save_error: null,
      save_message: null,
      saving: false,
    };
  }

  function mergeSavedQuestionPanels(
    currentPanels: QuestionDraftPanel[],
    savedPanels: QuestionDraftPanel[]
  ): QuestionDraftPanel[] {
    const currentByTemplateId = new Map(
      currentPanels
        .filter((panel) => panel.question_template_id)
        .map((panel) => [String(panel.question_template_id), panel])
    );
    const currentByQuestionNo = new Map(
      currentPanels
        .filter((panel) => Number(panel.question_no) > 0)
        .map((panel) => [Number(panel.question_no), panel])
    );
    const savedQuestionNos = new Set(savedPanels.map((panel) => Number(panel.question_no)));
    const mergedSavedPanels = savedPanels.map((savedPanel) => {
      const current =
        currentByTemplateId.get(String(savedPanel.question_template_id)) ||
        currentByQuestionNo.get(Number(savedPanel.question_no));
      return {
        ...savedPanel,
        expected_answer_text: current?.expected_answer_text ?? savedPanel.expected_answer_text,
        save_message: current?.saving ? 'Đã lưu câu hỏi.' : current?.save_message,
        save_error: null,
        saving: false,
      };
    });
    const unsavedPanels = currentPanels.filter((panel) => {
      if (panel.is_saved) {
        return false;
      }
      const questionNo = Number(panel.question_no);
      return !Number.isFinite(questionNo) || !savedQuestionNos.has(questionNo);
    });
    return [...mergedSavedPanels, ...unsavedPanels].sort((a, b) => Number(a.question_no || 0) - Number(b.question_no || 0));
  }

  function computeSuggestedScore(panelCount: number): string {
    const totalScore = Number(selectedVersion?.total_score);
    if (!Number.isFinite(totalScore) || totalScore <= 0 || panelCount <= 0) {
      return '';
    }
    return (totalScore / panelCount).toFixed(2).replace(/\.00$/, '');
  }

  function nextQuestionNoFromPanels(panels: QuestionDraftPanel[]): number {
    const maxNo = panels.reduce((maxValue, panel) => {
      const parsed = Number(panel.question_no);
      return Number.isFinite(parsed) ? Math.max(maxValue, parsed) : maxValue;
    }, 0);
    return Math.max(1, maxNo + 1);
  }

  function applyQuestionCount(targetCount: number) {
    const safeCount = Math.min(100, Math.max(1, targetCount));
    setQuestionPanels((current) => {
      const savedPanels = current.filter((panel) => panel.is_saved);
      const unsavedPanels = current.filter((panel) => !panel.is_saved);
      if (safeCount < savedPanels.length) {
        setQuestionPanelError('Không thể giảm số câu hỏi nhỏ hơn số câu đã lưu. Hãy deactivate câu đã lưu trước.');
        return current;
      }
      setQuestionPanelError(null);
      const requiredUnsavedCount = safeCount - savedPanels.length;
      if (requiredUnsavedCount <= unsavedPanels.length) {
        return [...savedPanels, ...unsavedPanels.slice(0, requiredUnsavedCount)];
      }
      const nextPanels = [...savedPanels, ...unsavedPanels];
      let nextQuestionNo = nextQuestionNoFromPanels(nextPanels);
      const suggestedScore = computeSuggestedScore(safeCount);
      for (let index = unsavedPanels.length; index < requiredUnsavedCount; index += 1) {
        nextPanels.push(createQuestionPanelDraft(nextQuestionNo, suggestedScore));
        nextQuestionNo += 1;
      }
      return nextPanels;
    });
    setQuestionCount(String(safeCount));
  }

  function updateQuestionPanel(panelId: string, patch: Partial<QuestionDraftPanel>) {
    setQuestionPanels((current) =>
      current.map((panel) =>
        panel.panel_id === panelId
          ? {
              ...panel,
              ...patch,
            }
          : panel
      )
    );
  }

  async function handleSaveQuestionPanel(panel: QuestionDraftPanel) {
    const duplicateNos = new Set<number>();
    for (const currentPanel of questionPanels) {
      if (currentPanel.panel_id === panel.panel_id) {
        continue;
      }
      const parsedNo = Number(currentPanel.question_no);
      if (Number.isFinite(parsedNo) && parsedNo > 0) {
        duplicateNos.add(parsedNo);
      }
    }
    for (const savedNo of existingSavedQuestionNos) {
      if (Number(panel.question_no) !== savedNo || !panel.question_template_id) {
        duplicateNos.add(savedNo);
      }
    }
    const validationError = validateQuestionDraftForUx(panel, duplicateNos);
    if (validationError) {
      updateQuestionPanel(panel.panel_id, { saving: false, save_error: validationError, save_message: null });
      return;
    }
    updateQuestionPanel(panel.panel_id, { saving: true, save_error: null, save_message: null });
    const result = await onQuestionSaveDraft({
      question_template_id: panel.question_template_id,
      question_no: panel.question_no,
      question_title: panel.question_title,
      prompt_text: panel.prompt_text,
      question_type: panel.question_type,
      response_mode: panel.response_mode,
      render_component: panel.render_component,
      max_score: panel.max_score,
      grading_engine_code: panel.grading_engine_code,
      comparison_method: panel.comparison_method,
      expected_answer_text: panel.expected_answer_text,
      status: panel.status,
      required: panel.required,
      mcq_options_text: panel.mcq_options_text,
    });
    if (!result.ok) {
      updateQuestionPanel(panel.panel_id, {
        saving: false,
        save_error: result.error || 'Không thể lưu câu hỏi. Vui lòng thử lại.',
        save_message: null,
      });
      return;
    }
    updateQuestionPanel(panel.panel_id, {
      saving: false,
      save_error: null,
      save_message: result.message || 'Đã lưu câu hỏi.',
    });
  }

  useEffect(() => {
    if (!selectedExamVersionId) {
      questionPanelsVersionRef.current = '';
      setQuestionPanels([]);
      setQuestionCount('1');
      setQuestionPanelError(null);
      return;
    }
    const savedPanels = [...versionQuestions]
      .sort((a, b) => Number(a.question_no || 0) - Number(b.question_no || 0))
      .map((item) => fromSavedQuestion(item));
    const versionChanged = questionPanelsVersionRef.current !== selectedExamVersionId;
    questionPanelsVersionRef.current = selectedExamVersionId;
    setQuestionPanels((currentPanels) => {
      const nextPanels = versionChanged ? savedPanels : mergeSavedQuestionPanels(currentPanels, savedPanels);
      setQuestionCount((currentCount) =>
        String(
          versionChanged
            ? Math.max(1, savedPanels.length || 1)
            : Math.max(Number(currentCount) || 1, nextPanels.length || 1)
        )
      );
      return nextPanels;
    });
    setQuestionPanelError(null);
  }, [selectedExamVersionId, versionQuestions]);

  const handleUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedFile) {
      return;
    }
    await onUploadPaperAsset(selectedFile);
    setSelectedFile(null);
  };

  return (
    <>
      {(mode === 'blueprint' || mode === 'exam-version') ? (
        <ApiCoverageNotice status="connected">
          Đang sử dụng API /master-data/exams và /master-data/exams/{'{exam_id}'}/versions. Đề gốc (blueprint) đã được tách rời khỏi lớp học phần.
        </ApiCoverageNotice>
      ) : null}

      {mode === 'blueprint' ? (
        <section className="setup-card setup-card-wide">
        <div className="section-heading">
          <div>
            <h3>Đề gốc / Blueprint</h3>
            <p className="muted">
              Đề thi gốc (blueprint) dùng để soạn thảo cấu hình câu hỏi, thang điểm và cách chấm điểm. Bạn có thể tái sử dụng đề gốc này cho nhiều lớp học phần khác nhau khi thiết lập ca thi ở bước Delivery Setup.
            </p>
          </div>
        </div>
        <form className="setup-form" onSubmit={onExamSubmit}>
          <SelectInput
            id="exam-blueprint-selector"
            label="Đề gốc"
            options={[{ label: 'Tạo đề gốc mới', value: '' }, ...examOptions]}
            value={selectedExamId}
            onChange={onSelectExam}
          />
          <TextInput
            id="exam-code"
            label="Mã đề thi"
            placeholder="ACC101-MID"
            value={examForm.exam_code}
            onChange={(value) => onExamFormChange({ exam_code: value })}
            required
          />
          <TextInput
            id="exam-name"
            label="Tên đề thi"
            placeholder="Kế toán giữa kỳ"
            value={examForm.exam_name}
            onChange={(value) => onExamFormChange({ exam_name: value })}
            required
          />
          <div className="setup-status-note" style={{ marginTop: '0.25rem', marginBottom: '0.5rem' }}>
            <strong>Thông tin liên kết tùy chọn</strong>
            <p className="muted" style={{ margin: '0.35rem 0 0.75rem' }}>
              Lớp học phần chỉ là metadata tham khảo cho blueprint cũ, không còn là điều kiện bắt buộc để cập nhật đề gốc.
            </p>
            <SelectInput
              id="exam-class-section"
              label="Lớp học phần liên kết (tùy chọn)"
              options={[{ label: 'Không có / Không bắt buộc', value: '' }, ...classSectionOptions]}
              value={examForm.class_section_id}
              onChange={(value) => onExamFormChange({ class_section_id: value })}
            />
          </div>
          <SelectInput
            id="exam-assessment-type"
            label="Hình thức đánh giá"
            options={assessmentTypeOptions.length > 0 ? assessmentTypeOptions : [{ label: 'Chưa có hình thức đánh giá', value: '' }]}
            value={examForm.assessment_type_id}
            onChange={(value) => onExamFormChange({ assessment_type_id: value })}
          />
          <TextInput
            id="exam-description"
            label="Mô tả"
            placeholder="Ghi chú nội bộ cho đề thi"
            value={examForm.description}
            onChange={(value) => onExamFormChange({ description: value })}
          />
          <SelectInput
            id="exam-status"
            label="Trạng thái đề"
            options={[
              { label: 'DRAFT', value: 'DRAFT' },
              { label: 'READY', value: 'READY' },
              { label: 'ACTIVE', value: 'ACTIVE' },
            ]}
            value={examForm.exam_status}
            onChange={(value) => onExamFormChange({ exam_status: value })}
          />
          <div className="setup-form-actions">
            <button
              className="primary-button"
              type="submit"
              disabled={examSubmitting || assessmentTypeOptions.length === 0}
            >
              {examSubmitting ? 'Đang lưu...' : selectedExamId ? 'Cập nhật đề gốc' : 'Tạo đề gốc'}
            </button>
            <button
              className="ghost-button"
              type="button"
              onClick={() => {
                onSelectExam('');
                onExamFormChange(initialExamForm);
              }}
            >
              Tạo đề mới
            </button>
          </div>
          {assessmentTypeOptions.length === 0 ? (
            <div className="disabled-reason-container" style={{ marginTop: '1rem', padding: '0.75rem', borderRadius: '4px', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
              <p className="text-error" style={{ color: '#ef4444', fontSize: '0.875rem', fontWeight: 500, margin: 0 }}>
                Nút tạo/cập nhật đề bị vô hiệu hóa vì lý do sau:
              </p>
              <ul style={{ color: '#ef4444', fontSize: '0.875rem', margin: '0.25rem 0 0 1.25rem', padding: 0 }}>
                <li>Chưa có hình thức đánh giá nào khả dụng trên hệ thống.</li>
              </ul>
            </div>
          ) : null}
        </form>
        {examError ? <p className="form-error">{examError}</p> : null}
        {examMessage ? <p className="success-message">{examMessage}</p> : null}
      </section>
      ) : null}

      {mode === 'exam-version' ? (
        <>
      <section className="setup-card setup-card-wide">
        <div className="section-heading">
          <div>
            <h3>Phiên bản đề thi</h3>
            <p className="muted">
              Phiên bản đề thi (exam version) định nghĩa nội dung câu hỏi và cấu trúc đề thi cụ thể sẽ được áp dụng cho ca thi.
            </p>
          </div>
        </div>
      <form className="setup-form" onSubmit={onSubmit}>
        {!selectedExamId ? <p className="muted">Vui lòng chọn hoặc tạo đề gốc trước.</p> : null}
        <SelectInput
          id="exam-version-exam"
          label="Đề gốc / Blueprint"
          options={examOptions.length > 0 ? examOptions : [{ label: 'Chưa có đề thi', value: '' }]}
          value={selectedExamId}
          onChange={onSelectExam}
        />
        <SelectInput
          id="exam-version-working-selector"
          label="Phiên bản đề đang soạn"
          options={[{ label: 'Tạo phiên bản mới', value: '' }, ...versionOptions]}
          value={selectedExamVersionId}
          onChange={(value) => {
            onSelectExamVersion(value);
            if (!value) {
              onFormChange(initialVersionForm);
            }
          }}
        />
        <TextInput
          id="exam-version-label"
          label="Tên version"
          placeholder="VD: Version 1"
          value={versionForm.version_label}
          onChange={(value) => onFormChange({ version_label: value })}
        />
        <TextInput
          id="exam-version-duration"
          label="Thời lượng (phút)"
          type="number"
          required
          value={versionForm.duration_minutes}
          onChange={(value) => onFormChange({ duration_minutes: value })}
        />
        <TextInput
          id="exam-version-score"
          label="Tổng điểm"
          type="number"
          required
          value={versionForm.total_score}
          onChange={(value) => onFormChange({ total_score: value })}
        />
        <SelectInput
          id="exam-version-random"
          label="Randomization"
          options={[
            { label: 'FIXED', value: 'FIXED' },
            { label: 'RANDOM_FROM_BANK', value: 'RANDOM_FROM_BANK' },
            { label: 'PARAMETERIZED', value: 'PARAMETERIZED' },
            { label: 'HYBRID', value: 'HYBRID' },
          ]}
          value={versionForm.randomization_mode}
          onChange={(value) => onFormChange({ randomization_mode: value })}
        />
        <SelectInput
          id="exam-version-status"
          label="Trạng thái"
          options={[
            { label: 'DRAFT', value: 'DRAFT' },
            { label: 'UNDER_REVIEW', value: 'UNDER_REVIEW' },
          ]}
          value={versionForm.status}
          onChange={(value) => onFormChange({ status: value })}
        />
        <div className="setup-form-actions">
          <button className="primary-button" type="submit" disabled={submitting || !selectedExamId}>
            {submitting ? 'Đang lưu...' : selectedExamVersionId ? 'Cập nhật phiên bản đề' : 'Tạo version'}
          </button>
          <button
            className="ghost-button"
            type="button"
            onClick={() => {
              onSelectExamVersion('');
              onFormChange(initialVersionForm);
            }}
          >
            Nhập phiên bản mới
          </button>
        </div>
      </form>

      {submitError ? <p className="form-error">{submitError}</p> : null}
      {submitMessage ? <p className="success-message">{submitMessage}</p> : null}
      <div className="setup-status-note" data-testid="selected-version-editing-note">
        <strong>Phiên bản đang soạn:</strong>
        <span>
          {' '}
          {selectedExamVersionId
            ? `ID ${selectedExamVersionId} - ${asString(selectedVersion?.version_label, `Version ${asString(selectedVersion?.version_no)}`)}. Chỉnh các trường phía trên rồi bấm Cập nhật phiên bản đề.`
            : 'Đang tạo phiên bản mới.'}
        </span>
      </div>
      </section>

      <div className="master-data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Đề thi</th>
              <th>Version</th>
              <th>Thời lượng</th>
              <th>Tổng điểm</th>
              <th>Trạng thái</th>
              <th>Hành động</th>
            </tr>
          </thead>
          <tbody>
            {versions.length === 0 ? (
              <tr>
                <td colSpan={7}>Chưa có version cho đề thi đã chọn.</td>
              </tr>
            ) : (
              versions.map((version, index) => (
                <tr key={getId(version, 'exam_version_id') || `version-${index}`}>
                  {(() => {
                    const versionId = getId(version, 'exam_version_id');
                    const isSelected = versionId === selectedExamVersionId;
                    return (
                      <>
                  <td>{asString(version.exam_version_id)}</td>
                  <td>{asString(version.exam_code)}</td>
                  <td>{asString(version.version_label, `Version ${asString(version.version_no)}`)}</td>
                  <td>{formatMinutes(version.duration_seconds)}</td>
                  <td>{asString(version.total_score)}</td>
                  <td>
                    <StatusBadge value={asString(version.status)} />
                  </td>
                  <td>
                    <button type="button" className="ghost-button" onClick={() => onSelectExamVersion(versionId)}>
                      {isSelected ? 'Đang sửa' : 'Chọn để sửa'}
                    </button>
                  </td>
                      </>
                    );
                  })()}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      </>
      ) : null}

      {mode === 'delivery-type' ? (
      <section className="setup-card setup-card-wide">
        <div className="section-heading">
          <div>
            <h3>Dạng đề</h3>
            <p className="muted">Đề PDF/ảnh, sinh viên xem đề và bài được chấm thủ công bằng rubric.</p>
          </div>
        </div>
        <div className="setup-form setup-form-single">
          <SelectInput
            id="delivery-type-version-selector"
            label="Phiên bản đề"
            options={versionOptions.length > 0 ? versionOptions : [{ label: 'Chưa có phiên bản đề', value: '' }]}
            value={selectedExamVersionId}
            onChange={onSelectExamVersion}
          />
        </div>
        {!hasSelectedVersion ? <p className="muted">Vui lòng chọn hoặc tạo phiên bản đề trước.</p> : null}
        <div className="setup-status-note">
          <strong>Dạng hiện tại:</strong>
          <span> {deliveryContentType || asString(deliveryProfile?.delivery_mode, 'Chưa cấu hình')}</span>
        </div>
        <ul className="setup-inline-notes">
          <li>FORM_QUESTION_BASED: câu hỏi/form, không yêu cầu paper asset.</li>
          <li>VISUAL_PAPER_BASED: yêu cầu tài liệu PDF/ảnh ở bước Tài liệu đề thi và dùng chấm tay bằng MANUAL_RUBRIC.</li>
          <li>FILE_SUBMISSION_BASED: sinh viên nộp file bài làm, khác với paper asset.</li>
        </ul>
        <div className="setup-form setup-form-single">
          <SelectInput
            id="delivery-content-type"
            label="Dạng đề"
            options={deliveryContentTypeOptions}
            value={deliveryContentType}
            onChange={(value) => onDeliveryContentTypeChange(value as DeliveryContentType | '')}
            disabled={!selectedExamVersionId || profileSubmitting}
          />
        </div>
        <div className="setup-form-actions">
          <button
            type="button"
            className="primary-button"
            data-testid="save-delivery-content-type"
            disabled={!selectedExamVersionId || profileSubmitting}
            onClick={() => void onSaveDeliveryContentType()}
          >
            {profileSubmitting ? 'Đang lưu...' : 'Lưu dạng đề'}
          </button>
        </div>
        {profileError ? <p className="form-error">{profileError}</p> : null}
        {profileMessage ? <p className="success-message">{profileMessage}</p> : null}
      </section>
      ) : null}

      {mode === 'paper' ? (
      <section className="setup-card setup-card-wide exam-paper-upload-section">
        <div className="section-heading">
          <div>
            <h3>Tài liệu đề thi</h3>
            <p className="muted">Tài liệu PDF/ảnh được gắn vào phiên bản đề dùng cho ca thi, không phải file bài làm của sinh viên.</p>
          </div>
        </div>

        <div className="setup-form setup-form-single">
          <SelectInput
            id="exam-version-paper-selector"
            label="Version đề"
            options={versionOptions.length > 0 ? versionOptions : [{ label: 'Chưa có version', value: '' }]}
            value={selectedExamVersionId}
            onChange={onSelectExamVersion}
          />
          <div className="setup-status-note" data-testid="paper-active-status">
            {selectedExamVersionId
              ? hasActiveAsset
                ? 'Version đang chọn đã có paper active.'
                : 'Version đang chọn chưa có paper active.'
              : 'Cần chọn version để upload tài liệu đề thi.'}
          </div>
        </div>

        <p className="setup-warning">
          Tài liệu PDF/ảnh là tùy chọn, chỉ bắt buộc với dạng đề hiển thị bằng tài liệu.
        </p>
        <p className="setup-warning">
          Hiển thị dạng ảnh/PDF chỉ giảm khả năng sao chép văn bản; không ngăn được chụp màn hình.
        </p>

        <form className="setup-form setup-form-single" onSubmit={(event) => void handleUpload(event)}>
          <label htmlFor="exam-version-paper-file">
            Tệp đề thi (PDF/PNG/JPG/WEBP)
            <input
              id="exam-version-paper-file"
              data-testid="paper-upload-input"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp,application/pdf,image/png,image/jpeg,image/webp"
              disabled={!selectedExamVersionId || paperSubmitting}
              onChange={(event) => {
                setSelectedFile(event.target.files?.[0] ?? null);
              }}
            />
          </label>
          <div className="setup-form-actions">
            <button
              className="primary-button"
              data-testid="paper-upload-submit"
              type="submit"
              disabled={!selectedExamVersionId || !selectedFile || paperSubmitting}
            >
              {paperSubmitting ? 'Đang upload...' : 'Upload paper'}
            </button>
          </div>
        </form>

        {paperError ? <p className="form-error">{paperError}</p> : null}
        {paperMessage ? <p className="success-message">{paperMessage}</p> : null}
        {paperAssetsLoading ? <p className="muted">Đang tải danh sách paper asset...</p> : null}

        <div className="master-data-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Tệp gốc</th>
                <th>MIME</th>
                <th>Kích thước</th>
                <th>SHA-256 (prefix)</th>
                <th>Trạng thái</th>
                <th>Tạo lúc</th>
                <th>Hành động</th>
              </tr>
            </thead>
            <tbody>
              {paperAssets.length === 0 ? (
                <tr>
                  <td colSpan={7}>Chưa có paper asset cho version này.</td>
                </tr>
              ) : (
                paperAssets.map((asset, index) => (
                  <tr key={asset.paper_asset_id ?? `paper-asset-${index}`}>
                    <td>{asString(asset.original_filename)}</td>
                    <td>{asString(asset.mime_type)}</td>
                    <td>{formatFileSize(asset.file_size_bytes)}</td>
                    <td>{formatShaPrefix(asset.sha256_hash)}</td>
                    <td>
                      <StatusBadge value={asset.is_active ? 'ACTIVE' : 'RETIRED'} />
                    </td>
                    <td>{asString(asset.created_at)}</td>
                    <td>
                      {asset.is_active ? (
                        <button
                          type="button"
                          className="ghost-button"
                          onClick={() => void onRetirePaperAsset(Number(asset.paper_asset_id))}
                          disabled={paperSubmitting}
                        >
                          Retire
                        </button>
                      ) : (
                        <span className="muted">-</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
      ) : null}

      {mode === 'questions' ? (
      <section className="setup-card setup-card-wide" data-testid="question-authoring-section">
        <div className="section-heading">
          <div>
            <h3>Câu hỏi / Nội dung đề theo câu</h3>
            <p className="muted">
              Soạn câu hỏi theo từng câu cho version đang chọn. Mỗi câu có form làm bài, cấu hình chấm và đáp án mong đợi riêng.
            </p>
          </div>
        </div>
        <div className="setup-form setup-form-single">
          <SelectInput
            id="question-working-version-selector"
            label="Phiên bản đề đang soạn"
            options={versionOptions.length > 0 ? versionOptions : [{ label: 'Chưa có phiên bản đề', value: '' }]}
            value={selectedExamVersionId}
            onChange={onSelectExamVersion}
          />
        </div>
        <div className="setup-status-note" data-testid="question-preset-intro">
          <strong>Tóm tắt preset:</strong>
          <ul className="setup-inline-notes">
            {questionPresetIntro.map((preset) => (
              <li key={preset.type}>
                {preset.type}: Form làm bài {preset.response}; Cách chấm {preset.grading}; Đáp án {preset.expected.toLowerCase()}.
              </li>
            ))}
          </ul>
        </div>
        <div className="setup-form setup-form-single">
          <TextInput
            id="question-count-input"
            label="Số câu hỏi"
            type="number"
            value={questionCount}
            onChange={(value) => setQuestionCount(value)}
            required
          />
          <div className="setup-form-actions">
            <button
              type="button"
              className="primary-button"
              onClick={() => applyQuestionCount(Number(questionCount || 1))}
              disabled={!selectedExamVersionId}
            >
              Tạo khung câu hỏi
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => applyQuestionCount((Number(questionCount || 1) || 1) + 1)}
              disabled={!selectedExamVersionId}
            >
              Thêm 1 khung
            </button>
            <button
              type="button"
              className="ghost-button"
              onClick={() => setShowAdvancedQuestionConfig((current) => !current)}
            >
              {showAdvancedQuestionConfig ? 'Ẩn cấu hình nâng cao' : 'Cấu hình nâng cao'}
            </button>
          </div>
        </div>
        {questionPanelError ? <p className="form-error">{questionPanelError}</p> : null}

        <div className="question-panel-list" data-testid="question-panels-generated">
          {questionPanels.map((panel, index) => (
            <section key={panel.panel_id} className="setup-card setup-card-wide question-panel-card">
              <div className="section-heading">
                <div>
                  <h4>{`Câu ${index + 1}`}</h4>
                  <p className="muted">
                    {panel.is_saved ? 'Đã lưu' : 'Khung nháp chưa lưu'} · {questionTypeLabel(panel.question_type)} · Chấm:{' '}
                    {panel.grading_engine_code || '-'}
                  </p>
                </div>
                <StatusBadge value={panel.status || 'DRAFT'} />
              </div>
              <div className="setup-form">
                <TextInput
                  id={`panel-question-title-${panel.panel_id}`}
                  label="question_title"
                  value={panel.question_title}
                  onChange={(value) => updateQuestionPanel(panel.panel_id, { question_title: value })}
                  required
                />
                <label htmlFor={`panel-prompt-${panel.panel_id}`}>
                  prompt_text
                  <textarea
                    id={`panel-prompt-${panel.panel_id}`}
                    rows={3}
                    value={panel.prompt_text}
                    onChange={(event) => updateQuestionPanel(panel.panel_id, { prompt_text: event.target.value })}
                    required
                  />
                </label>
                <SelectInput
                  id={`panel-question-type-${panel.panel_id}`}
                  label="Loại câu hỏi"
                  options={[
                    { label: 'TEXTAREA', value: 'TEXTAREA' },
                    { label: 'TEXTBOX_SQL', value: 'TEXTBOX_SQL' },
                    { label: 'FILE_UPLOAD', value: 'FILE_UPLOAD' },
                    { label: 'MCQ_SINGLE', value: 'MCQ_SINGLE' },
                  ]}
                  value={panel.question_type}
                  onChange={(value) => {
                    const defaults = questionTypeDefaults(value as VersionQuestionForm['question_type']);
                    updateQuestionPanel(panel.panel_id, {
                      question_type: value as VersionQuestionForm['question_type'],
                      response_mode: defaults.response_mode,
                      render_component: defaults.render_component,
                      grading_engine_code: defaults.grading_engine_code,
                      comparison_method: defaults.comparison_method,
                    });
                  }}
                />
                <div className="setup-status-note" data-testid={`panel-response-profile-${index + 1}`}>
                  <strong>Form làm bài</strong>
                  <p>{questionResponseProfileLabel(panel)}</p>
                </div>
                <TextInput
                  id={`panel-max-score-${panel.panel_id}`}
                  label="max_score"
                  type="number"
                  value={panel.max_score}
                  onChange={(value) => updateQuestionPanel(panel.panel_id, { max_score: value })}
                />
                {showAdvancedQuestionConfig ? (
                  <>
                    <TextInput
                      id={`panel-response-mode-${panel.panel_id}`}
                      label="response_mode"
                      value={panel.response_mode}
                      onChange={(value) => updateQuestionPanel(panel.panel_id, { response_mode: value })}
                    />
                    <TextInput
                      id={`panel-render-component-${panel.panel_id}`}
                      label="render_component"
                      value={panel.render_component}
                      onChange={(value) => updateQuestionPanel(panel.panel_id, { render_component: value })}
                    />
                    <TextInput
                      id={`panel-grading-engine-${panel.panel_id}`}
                      label="grading_engine_code"
                      value={panel.grading_engine_code}
                      onChange={(value) => updateQuestionPanel(panel.panel_id, { grading_engine_code: value })}
                    />
                    <TextInput
                      id={`panel-comparison-method-${panel.panel_id}`}
                      label="comparison_method"
                      value={panel.comparison_method}
                      onChange={(value) => updateQuestionPanel(panel.panel_id, { comparison_method: value })}
                    />
                  </>
                ) : null}
                {panel.question_type === 'TEXTBOX_SQL' || panel.question_type === 'MCQ_SINGLE' ? (
                  <label htmlFor={`panel-expected-answer-${panel.panel_id}`}>
                    Đáp án mẫu / câu trả lời đúng (admin-only)
                    <textarea
                      id={`panel-expected-answer-${panel.panel_id}`}
                      rows={3}
                      value={panel.expected_answer_text}
                      onChange={(event) =>
                        updateQuestionPanel(panel.panel_id, { expected_answer_text: event.target.value })
                      }
                    />
                  </label>
                ) : null}
                {panel.question_type === 'MCQ_SINGLE' ? (
                  <label htmlFor={`panel-mcq-options-${panel.panel_id}`}>
                    Tùy chọn MCQ (mỗi dòng 1 lựa chọn)
                    <textarea
                      id={`panel-mcq-options-${panel.panel_id}`}
                      rows={3}
                      value={panel.mcq_options_text}
                      onChange={(event) => updateQuestionPanel(panel.panel_id, { mcq_options_text: event.target.value })}
                    />
                  </label>
                ) : null}
                <div className="setup-form-actions">
                  <button
                    type="button"
                    className="primary-button"
                    onClick={() => void handleSaveQuestionPanel(panel)}
                    disabled={panel.saving || !selectedExamVersionId}
                  >
                    {panel.saving ? 'Đang lưu...' : 'Lưu câu hỏi'}
                  </button>
                  {!panel.is_saved ? (
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() =>
                        setQuestionPanels((current) => current.filter((currentPanel) => currentPanel.panel_id !== panel.panel_id))
                      }
                    >
                      Xóa khung
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() =>
                        void handleSaveQuestionPanel({
                          ...panel,
                          status: 'DRAFT',
                        })
                      }
                    >
                      Hủy kích hoạt (DRAFT)
                    </button>
                  )}
                </div>
                {panel.save_error ? <p className="form-error">{panel.save_error}</p> : null}
                {panel.save_message ? <p className="success-message">{panel.save_message}</p> : null}
              </div>
            </section>
          ))}
          {!questionPanels.length ? (
            <section className="setup-card">
              <p className="muted">Chưa có khung câu hỏi. Hãy nhập Số câu hỏi và bấm Tạo khung câu hỏi.</p>
            </section>
          ) : null}
        </div>

        {!questionPanels.length ? (
        <form className="setup-form" onSubmit={onQuestionSubmit}>
          <TextInput
            id="question-template-id"
            label="ID câu hỏi (để trống = tạo mới)"
            value={questionForm.question_template_id}
            onChange={(value) => onQuestionFormChange({ question_template_id: value })}
          />
          <TextInput
            id="question-no"
            label="Số câu"
            type="number"
            value={questionForm.question_no}
            onChange={(value) => onQuestionFormChange({ question_no: value })}
            required
          />
          <TextInput
            id="question-title"
            label="Tiêu đề câu hỏi"
            value={questionForm.question_title}
            onChange={(value) => onQuestionFormChange({ question_title: value })}
            required
          />
          <label htmlFor="question-prompt">
            Nội dung câu hỏi
            <textarea
              id="question-prompt"
              rows={4}
              value={questionForm.prompt_text}
              onChange={(event) => onQuestionFormChange({ prompt_text: event.target.value })}
              required
            />
          </label>
          <SelectInput
            id="question-type"
            label="Loại câu hỏi"
            options={[
              { label: 'TEXTAREA', value: 'TEXTAREA' },
              { label: 'TEXTBOX_SQL', value: 'TEXTBOX_SQL' },
              { label: 'FILE_UPLOAD', value: 'FILE_UPLOAD' },
              { label: 'MCQ_SINGLE', value: 'MCQ_SINGLE' },
            ]}
            value={questionForm.question_type}
            onChange={(value) => onQuestionTypeChange(value as VersionQuestionForm['question_type'])}
          />
          <div className="setup-status-note">
            <strong>Tóm tắt preset:</strong>
            <ul className="setup-inline-notes">
              <li>Form làm bài: {questionPresetSummary(questionForm).response}</li>
              <li>Cách chấm: {questionPresetSummary(questionForm).grading}</li>
              <li>Đáp án bắt buộc: {questionPresetSummary(questionForm).expected}</li>
            </ul>
          </div>
          {showAdvancedQuestionConfig ? (
            <>
              <TextInput
                id="question-response-mode"
                label="response_mode"
                value={questionForm.response_mode}
                onChange={(value) => onQuestionFormChange({ response_mode: value })}
              />
              <TextInput
                id="question-render-component"
                label="render_component"
                value={questionForm.render_component}
                onChange={(value) => onQuestionFormChange({ render_component: value })}
              />
            </>
          ) : null}
          <TextInput
            id="question-max-score"
            label="Điểm tối đa"
            type="number"
            value={questionForm.max_score}
            onChange={(value) => onQuestionFormChange({ max_score: value })}
            required
          />
          {showAdvancedQuestionConfig ? (
            <>
              <TextInput
                id="question-grading-engine"
                label="grading_engine_code"
                value={questionForm.grading_engine_code}
                onChange={(value) => onQuestionFormChange({ grading_engine_code: value })}
                required
              />
              <TextInput
                id="question-comparison-method"
                label="comparison_method"
                value={questionForm.comparison_method}
                onChange={(value) => onQuestionFormChange({ comparison_method: value })}
                required
              />
            </>
          ) : null}
          <label htmlFor="question-expected-answer">
            Đáp án tham chiếu / expected answer
            <textarea
              id="question-expected-answer"
              rows={3}
              value={questionForm.expected_answer_text}
              onChange={(event) => onQuestionFormChange({ expected_answer_text: event.target.value })}
            />
          </label>
          {questionForm.question_type === 'MCQ_SINGLE' ? (
            <label htmlFor="question-mcq-options">
              Tùy chọn MCQ (mỗi dòng 1 lựa chọn)
              <textarea
                id="question-mcq-options"
                rows={4}
                value={questionForm.mcq_options_text}
                onChange={(event) => onQuestionFormChange({ mcq_options_text: event.target.value })}
              />
            </label>
          ) : null}
          <SelectInput
            id="question-status"
            label="Trạng thái"
            options={[
              { label: 'DRAFT', value: 'DRAFT' },
              { label: 'ACTIVE', value: 'ACTIVE' },
            ]}
            value={questionForm.status}
            onChange={(value) => onQuestionFormChange({ status: value })}
          />
          <label htmlFor="question-required">
            Bắt buộc trả lời
            <input
              id="question-required"
              type="checkbox"
              checked={questionForm.required}
              onChange={(event) => onQuestionFormChange({ required: event.target.checked })}
            />
          </label>
          <div className="setup-form-actions">
            <button className="primary-button" type="submit" disabled={!selectedExamVersionId || questionSubmitting}>
              {questionSubmitting
                ? 'Đang lưu...'
                : questionForm.question_template_id
                  ? 'Cập nhật câu hỏi'
                  : 'Thêm câu hỏi'}
            </button>
          </div>
        </form>
        ) : null}
        {questionError ? <p className="form-error">{questionError}</p> : null}
        {questionMessage ? <p className="success-message">{questionMessage}</p> : null}

        <div className="setup-status-note" data-testid="question-readiness-summary">
          <strong>Kiểm tra readiness theo câu:</strong>
          <span>{questionReadiness.ready ? ' Đủ điều kiện.' : ' Chưa đủ điều kiện.'}</span>
          {!questionReadiness.ready && questionReadiness.missing_items.length > 0 ? (
            <ul className="setup-inline-notes">
              {questionReadiness.missing_items.map((item, index) => (
                <li key={`missing-item-${index}`}>{asString(item.code, asString(item.message, 'missing'))}</li>
              ))}
            </ul>
          ) : null}
        </div>

        <div className="master-data-table-wrap">
          <table>
            <thead>
              <tr>
                <th>question_no</th>
                <th>prompt</th>
                <th>response_mode</th>
                <th>grading_engine_code</th>
                <th>max_score</th>
                <th>status</th>
                <th>Hành động</th>
              </tr>
            </thead>
            <tbody>
              {versionQuestions.length === 0 ? (
                <tr>
                  <td colSpan={7}>Chưa có câu hỏi cho version này.</td>
                </tr>
              ) : (
                versionQuestions.map((item) => (
                  <tr key={item.question_template_id}>
                    <td>{item.question_no}</td>
                    <td>{item.prompt_text}</td>
                    <td>{item.response_mode}</td>
                    <td>{item.grading_engine_code}</td>
                    <td>{item.max_score}</td>
                    <td>
                      <StatusBadge value={item.status} />
                    </td>
                    <td>
                      <button type="button" className="ghost-button" onClick={() => onQuestionEdit(item)}>
                        Sửa
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
      ) : null}

      {mode === 'response-profile' ? (
      <section className="setup-card setup-card-wide" data-testid="file-upload-preset-section">
        <div className="section-heading">
          <div>
            <h3>Form làm bài</h3>
            <p className="muted">
              Response profile quyết định sinh viên nhìn thấy gì và trả lời bằng cách nào. Tạm thời metadata render được lưu cùng profile hiện có.
            </p>
          </div>
        </div>
        <ul className="setup-inline-notes">
          <li>Nộp bài bằng tệp đính kèm</li>
          <li>Chấm thủ công theo rubric</li>
          <li>Không capture sau khi nộp</li>
        </ul>
        <div className="setup-form-actions">
          <button
            type="button"
            className="primary-button"
            data-testid="configure-file-upload-manual-grading"
            disabled={!selectedExamVersionId || profileSubmitting}
            onClick={() => void onConfigureFileUploadManualGrading()}
          >
            {profileSubmitting ? 'Đang cấu hình...' : 'Cấu hình nộp tệp + chấm thủ công'}
          </button>
          <button
            type="button"
            className="secondary-button"
            data-testid="create-file-upload-placeholder"
            disabled={!selectedExamVersionId || profileSubmitting}
            onClick={() => void onCreatePlaceholderQuestion()}
          >
            Tạo câu nộp tệp bài làm
          </button>
          <button
            type="button"
            className="secondary-button"
            data-testid="apply-file-upload-preset"
            disabled={!selectedExamVersionId || profileSubmitting}
            onClick={() => void onApplyFileUploadPreset()}
          >
            {profileSubmitting ? 'Đang áp dụng...' : 'Áp dụng cấu hình file upload'}
          </button>
        </div>
        {!gradingProfiles.length ? (
          <p className="form-error">Chưa có câu hỏi cấu trúc cho version này. Hãy tạo câu nộp tệp bài làm trước.</p>
        ) : null}
        {profileError ? <p className="form-error">{profileError}</p> : null}
        {profileMessage ? <p className="success-message">{profileMessage}</p> : null}
        {profileLoading ? <p className="muted">Đang tải cấu hình profile...</p> : null}
      </section>
      ) : null}

      {mode === 'grading-profile' ? (
      <section className="setup-card setup-card-wide">
        <div className="section-heading">
          <div>
            <h3>Cấu hình chấm</h3>
            <p className="muted">Grading profile quyết định cách chấm điểm theo câu. Form làm bài được điều khiển ở tab Form làm bài.</p>
          </div>
        </div>
        {profileError ? <p className="form-error">{profileError}</p> : null}
        {profileMessage ? <p className="success-message">{profileMessage}</p> : null}
        {profileLoading ? <p className="muted">Đang tải cấu hình profile...</p> : null}
        <div className="master-data-table-wrap">
          <h4>Delivery profile</h4>
          <table>
            <thead>
              <tr>
                <th>Nhóm</th>
                <th>Giá trị</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>delivery_mode</td>
                <td>{asString(deliveryProfile?.delivery_mode)}</td>
              </tr>
              <tr>
                <td>primary_answer_source</td>
                <td>{asString(deliveryProfile?.primary_answer_source)}</td>
              </tr>
              <tr>
                <td>requires_capture</td>
                <td>{deliveryProfile ? String(Boolean(deliveryProfile.requires_capture)) : '-'}</td>
              </tr>
              <tr>
                <td>capture_timing</td>
                <td>{asString(deliveryProfile?.capture_timing)}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="master-data-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Question template</th>
                <th>Input source</th>
                <th>Grading engine</th>
                <th>Comparison</th>
                <th>Trạng thái</th>
                <th>Hành động</th>
              </tr>
            </thead>
            <tbody>
              {gradingProfiles.length === 0 ? (
                <tr>
                  <td colSpan={6}>Chưa có question grading profile cho version này.</td>
                </tr>
              ) : (
                gradingProfiles.map((profile) => (
                  <tr key={profile.question_grading_profile_id}>
                    <td>{asString(profile.question_template_id)}</td>
                    <td>{asString(profile.input_source)}</td>
                    <td>{asString(profile.grading_engine_code)}</td>
                    <td>{asString(profile.comparison_method)}</td>
                    <td>
                      <StatusBadge value={asString(profile.status)} />
                    </td>
                    <td>
                      {String(profile.status).toUpperCase() === 'ACTIVE' ? (
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={profileSubmitting}
                          onClick={() => void onRetireGradingProfile(Number(profile.question_grading_profile_id))}
                        >
                          Retire
                        </button>
                      ) : (
                        <span className="muted">-</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
      ) : null}

      {mode === 'expected-answer' ? (
      <section className="setup-card setup-card-wide">
        <div className="section-heading">
          <div>
            <h3>Đáp án</h3>
            <p className="muted">Theo dõi trạng thái expected answer/reference solution cho exam version đang chọn.</p>
          </div>
        </div>
        <div className="setup-status-note" data-testid="expected-answer-section">
          <strong>Đáp án / Expected answer</strong>
          <span>
            Đáp án thuộc reference solution hoặc generated expected answer snapshot của version. Student runtime chỉ nhận response profile và metadata chấm an toàn, không nhận answer key.
          </span>
        </div>
        <div className="setup-status-note">
          <strong>Readiness theo đáp án:</strong>
          <span>
            {' '}
            {questionReadiness.missing_items.some((item) => String(item.code) === 'question_expected_answer_missing')
              ? 'Còn câu auto-graded thiếu expected answer.'
              : 'Không phát hiện thiếu expected answer cho câu auto-graded.'}
          </span>
        </div>
      </section>
      ) : null}

      {mode === 'version-readiness' ? (
      <section className="setup-card setup-card-wide" data-testid="version-readiness-section">
        <div className="section-heading">
          <div>
            <h3>Version readiness</h3>
            <p className="muted">
              ACTIVE là trạng thái của đề gốc/blueprint. PUBLISHED là trạng thái của phiên bản đề; publish version chỉ chạy sau khi
              blueprint đã ACTIVE.
            </p>
          </div>
        </div>
        {!selectedExamVersionId ? <p className="muted">Vui lòng chọn hoặc tạo phiên bản đề trước.</p> : null}
        <div className="setup-status-note">
          <strong>Đề gốc / blueprint:</strong>
          <span>
            {' '}
            {selectedExam
              ? `${asString(selectedExam.exam_code)} - ${asString(selectedExam.exam_name)} · ${asString(
                  selectedExam.exam_status ?? selectedExam.status,
                  'DRAFT'
                )}`
              : '-'}
          </span>
        </div>
        <div className="setup-status-note">
          <strong>Phiên bản đề:</strong>
          <span> {selectedVersion ? `${asString(selectedVersion.version_label, `Version ${asString(selectedVersion.version_no)}`)} · ${asString(selectedVersion.status)}` : '-'}</span>
        </div>
        <div className="setup-status-note">
          <strong>Câu hỏi:</strong>
          <span> {versionQuestions.length} câu đang tải từ API.</span>
        </div>
        <div className="setup-status-note">
          <strong>Form làm bài / Cấu hình chấm / Đáp án:</strong>
          <span> {questionReadiness.ready ? 'Đạt kiểm tra cấu hình theo câu.' : 'Chưa đạt kiểm tra cấu hình theo câu.'}</span>
          {!questionReadiness.ready && questionReadiness.missing_items.length > 0 ? (
            <ul className="setup-inline-notes">
              {questionReadiness.missing_items.map((item, index) => (
                <li key={`version-readiness-missing-${index}`}>{asString(item.code, asString(item.message, 'missing'))}</li>
              ))}
            </ul>
          ) : null}
        </div>
        <div className="setup-status-note">
          <strong>Tài liệu đề thi:</strong>
          <span> {hasActiveAsset ? 'Có paper asset active.' : 'Chưa có paper asset active. Chỉ bắt buộc với VISUAL_PAPER_BASED.'}</span>
        </div>
        {selectedExamVersionId && selectedVersion ? (
          <div className="setup-action-row">
            <button
              type="button"
              className="btn-primary"
              disabled={
                versionPublishing ||
                !selectedExamVersionId ||
                ['PUBLISHED', 'RETIRED', 'VOIDED'].includes(asString(selectedVersion.status ?? selectedVersion.exam_version_status).toUpperCase())
              }
              onClick={() => void onPublishVersion()}
            >
              {versionPublishing ? 'Đang publish...' : 'Publish phiên bản đề'}
            </button>
            {asString(selectedVersion.status ?? selectedVersion.exam_version_status).toUpperCase() === 'PUBLISHED' ? (
              <p className="setup-success">Phiên bản này đã được publish.</p>
            ) : null}
            {['RETIRED', 'VOIDED'].includes(asString(selectedVersion.status ?? selectedVersion.exam_version_status).toUpperCase()) ? (
              <p className="form-error">Không thể publish lại version đã retired/voided; hãy tạo version mới.</p>
            ) : null}
            {versionPublishMessage ? <p className="setup-success">{versionPublishMessage}</p> : null}
            {versionPublishError ? <p className="form-error">{versionPublishError}</p> : null}
          </div>
        ) : null}
        {versionPublishBlockers.length > 0 ? (
          <div className="master-data-table-wrap" data-testid="publish-blockers-table">
            <table>
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Message</th>
                  <th>Severity / status</th>
                  <th>Khu vực</th>
                  <th>Hành động</th>
                </tr>
              </thead>
              <tbody>
                {versionPublishBlockers.map((blocker, index) => {
                  const hasMappedSection = Boolean(blocker.sectionKey);
                  const isExamNotActiveBlocker = blocker.code.trim().toLowerCase() === 'exam_not_active';
                  return (
                    <tr key={`${blocker.code}-${index}`}>
                      <td>{blocker.code}</td>
                      <td>{blocker.message}</td>
                      <td>{blocker.severity || blocker.status || '-'}</td>
                      <td>{blocker.sectionTitle || '-'}</td>
                      <td>
                        {isExamNotActiveBlocker ? (
                          <button
                            type="button"
                            className="ghost-button"
                            disabled={examActivationLoading}
                            onClick={() => void onActivateExamBlueprint()}
                          >
                            {examActivationLoading ? 'Đang kích hoạt...' : 'Kích hoạt đề gốc'}
                          </button>
                        ) : hasMappedSection ? (
                          <button type="button" className="ghost-button" onClick={() => blocker.sectionKey && onSelect(blocker.sectionKey)}>
                            Sửa cấu hình
                          </button>
                        ) : (
                          <span className="muted">-</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
      ) : null}
    </>
  );
}

function SittingsPanelMvp({
  versions,
  sittings,
  selectedSittingId,
  sittingForm,
  sittingSubmitting,
  sittingMessage,
  sittingError,
  onFormChange,
  onSubmit,
  onSelectSitting,
  onNewSitting,
}: {
  versions: ExamSetupRow[];
  sittings: SetupSitting[];
  selectedSittingId: string;
  sittingForm: SittingForm;
  sittingSubmitting: boolean;
  sittingMessage: string | null;
  sittingError: string | null;
  onFormChange: (patch: Partial<SittingForm>) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onSelectSitting: (value: string) => void;
  onNewSitting: () => void;
}) {
  const versionOptions = versions.map((version) => ({
    value: getId(version, 'exam_version_id'),
    label: `${asString(version.exam_code)} - ${asString(version.version_label, `Version ${asString(version.version_no)}`)}`,
  }));
  const selectedSitting = sittings.find((sitting) => String(sitting.exam_sitting_id) === selectedSittingId);
  const isEditingExistingSitting = Boolean(selectedSittingId);
  const lifecycleStatus = asString(selectedSitting?.sitting_status, sittingForm.status || 'DRAFT');

  return (
    <>
      <ApiCoverageNotice status="connected">
        API delivery setup đã nối cho tạo/list/sửa ca thi. Backend hiện vẫn yêu cầu gắn tạm một exam version khi tạo ca thi.
      </ApiCoverageNotice>
      {sittings.length > 0 ? (
        <label htmlFor="sitting-working-selector">
          Chọn ca thi đang cấu hình
          <select id="sitting-working-selector" value={selectedSittingId} onChange={(event) => onSelectSitting(event.target.value)}>
            <option value="">Tạo ca thi mới</option>
            {sittings.map((sitting) => (
              <option key={sitting.exam_sitting_id} value={String(sitting.exam_sitting_id)}>
                {sitting.sitting_code} - {sitting.sitting_name}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {versionOptions.length === 0 ? <p className="form-error">Cần tạo/publish đề thi trước khi tạo ca thi.</p> : null}
      <form className="setup-form" onSubmit={onSubmit}>
        <TextInput
          id="sitting-code-mvp"
          label="Mã ca thi"
          value={sittingForm.sitting_code}
          onChange={(value) => onFormChange({ sitting_code: value })}
          required={!selectedSittingId}
          placeholder={selectedSittingId ? 'Không sửa mã ca qua API hiện tại' : 'ACC101-2026-MID-AM'}
        />
        {selectedSittingId ? (
          <p className="muted">Mã ca thi hiện chưa có endpoint sửa; các trường tên và thời gian có thể cập nhật.</p>
        ) : null}
        {isEditingExistingSitting ? (
          <>
            <p className="muted">Đổi trạng thái bằng khu vực Chuẩn bị/Mở ca thi.</p>
            <div className="setup-status-note">
              <strong>Trạng thái hiện tại:</strong>
              <span> {lifecycleStatus}</span>
            </div>
          </>
        ) : null}
        <TextInput
          id="sitting-name-mvp"
          label="Tên ca thi"
          placeholder="Ca sáng - ACC101"
          value={sittingForm.sitting_name}
          onChange={(value) => onFormChange({ sitting_name: value })}
          required
        />
        {!selectedSittingId ? (
          <SelectInput
            id="sitting-exam-version-mvp"
            label="Phiên bản đề áp dụng"
            options={versionOptions.length > 0 ? versionOptions : [{ label: 'Chưa có exam version', value: '' }]}
            value={sittingForm.exam_version_id}
            onChange={(value) => onFormChange({ exam_version_id: value })}
          />
        ) : null}
        <TextInput
          id="sitting-start-mvp"
          label="Bắt đầu"
          type="datetime-local"
          value={sittingForm.scheduled_start_at}
          onChange={(value) => onFormChange({ scheduled_start_at: value })}
          required
        />
        <TextInput
          id="sitting-end-mvp"
          label="Kết thúc"
          type="datetime-local"
          value={sittingForm.scheduled_end_at}
          onChange={(value) => onFormChange({ scheduled_end_at: value })}
          required
        />
        <SelectInput
          id="sitting-status-mvp"
          label="Trạng thái (vòng đời)"
          options={[
            { label: 'DRAFT', value: 'DRAFT' },
            { label: 'READY', value: 'READY' },
          ]}
          value={sittingForm.status}
          onChange={(value) => onFormChange({ status: value })}
          disabled={isEditingExistingSitting}
        />
        <div className="setup-form-actions">
          <button className="primary-button" type="submit" disabled={sittingSubmitting || (!selectedSittingId && versionOptions.length === 0)}>
            {sittingSubmitting ? 'Đang lưu...' : selectedSittingId ? 'Cập nhật ca thi' : 'Tạo ca thi'}
          </button>
          <button className="ghost-button" type="button" onClick={onNewSitting}>
            Nhập ca thi mới
          </button>
        </div>
      </form>
      {sittingError ? <p className="form-error">{sittingError}</p> : null}
      {sittingMessage ? <p className="success-message">{sittingMessage}</p> : null}
      <SimpleTable
        columns={[
          ['sitting_code', 'Mã ca'],
          ['sitting_name', 'Tên ca'],
          ['exam_version_label', 'Đề/version'],
          ['scheduled_start_at', 'Bắt đầu'],
          ['scheduled_end_at', 'Kết thúc'],
          ['sitting_status', 'Trạng thái'],
        ]}
        rows={sittings as unknown as ExamSetupRow[]}
        emptyText="Chưa có ca thi."
      />
    </>
  );
}

function RoomsPanel({
  rooms,
  sittings,
  selectedSittingId,
  sittingRooms,
  roomForm,
  editingRoomId,
  submitting,
  message,
  error,
  onFormChange,
  onCreate,
  onEdit,
  onCancel,
  onNew,
}: {
  rooms: ExamSetupRow[];
  sittings: SetupSitting[];
  selectedSittingId: string;
  sittingRooms: DeliverySittingRoom[];
  roomForm: SittingRoomForm;
  editingRoomId: string;
  submitting: boolean;
  message: string | null;
  error: string | null;
  onFormChange: (patch: Partial<SittingRoomForm>) => void;
  onCreate: (event: FormEvent<HTMLFormElement>) => void;
  onEdit: (room: DeliverySittingRoom) => void;
  onCancel: (examSittingRoomId: number) => Promise<void>;
  onNew: () => void;
}) {
  const roomOptions = rooms.map((room) => ({
    value: getId(room, 'room_id'),
    label: `${asString(room.room_code)} - ${asString(room.room_name)}`,
  }));
  const sitting = sittings.find((item) => String(item.exam_sitting_id) === selectedSittingId);
  const canAddRoom = Boolean(selectedSittingId && (editingRoomId || roomForm.room_id));
  return (
    <>
      <ApiCoverageNotice status="connected">Phòng thi trong ca dùng API `/delivery/exam-sittings/{'{id}'}/rooms`.</ApiCoverageNotice>
      {sitting ? <p className="muted">Ca thi: {sitting.sitting_code} - {sitting.sitting_name}</p> : null}
      {selectedSittingId && roomOptions.length === 0 ? <p className="muted">Chưa có phòng thi trong danh mục phòng. Hãy tạo phòng/lab trước.</p> : null}
      {selectedSittingId ? (
        <form className="setup-form" onSubmit={onCreate}>
          <SelectInput
            id="room-id"
            label="Phòng thi"
            options={roomOptions}
            value={roomForm.room_id}
            onChange={(v) => onFormChange({ room_id: v })}
            disabled={Boolean(editingRoomId)}
            placeholder="Chọn phòng thi trong danh mục"
          />
          <TextInput id="capacity-allocated" label="Sức chứa phân bổ" type="number" value={roomForm.capacity_allocated} onChange={(v) => onFormChange({ capacity_allocated: v })} />
          <SelectInput
            id="room-status"
            label="Trạng thái"
            options={[{ label: 'PLANNED', value: 'PLANNED' }, { label: 'READY', value: 'READY' }, { label: 'OPEN', value: 'OPEN' }]}
            value={roomForm.room_status}
            onChange={(v) => onFormChange({ room_status: v })}
          />
          <div className="setup-form-actions">
            <button className="primary-button" type="submit" disabled={submitting || !canAddRoom}>{editingRoomId ? 'Cập nhật phòng thi' : 'Thêm phòng thi'}</button>
            {editingRoomId ? <button className="ghost-button" type="button" onClick={onNew}>Nhập phòng mới</button> : null}
          </div>
        </form>
      ) : <p className="muted">Hãy chọn một ca thi ở tab `Ca thi`.</p>}
      {error ? <p className="form-error">{error}</p> : null}
      {message ? <p className="success-message">{message}</p> : null}
      <SimpleTable
        columns={[['room_code', 'Mã phòng'], ['room_name', 'Tên phòng'], ['capacity_allocated', 'Sức chứa phân bổ'], ['room_status', 'Trạng thái']]}
        rows={sittingRooms as unknown as ExamSetupRow[]}
        emptyText="Chưa có phòng thi cho ca này."
        actions={(row) => (
          <div className="inline-actions">
            <button type="button" className="ghost-button" onClick={() => onEdit(row as unknown as DeliverySittingRoom)}>Sửa</button>
            <button type="button" className="ghost-button" onClick={() => void onCancel(Number(row.exam_sitting_room_id))}>Hủy</button>
          </div>
        )}
      />
    </>
  );
}

function ProctorsPanel({
  instructors,
  sittingRooms,
  proctors,
  selectedSittingId,
  form,
  editingProctorId,
  submitting,
  message,
  error,
  onFormChange,
  onCreate,
  onEdit,
  onCancel,
  onNew,
}: {
  instructors: ExamSetupRow[];
  sittingRooms: DeliverySittingRoom[];
  proctors: DeliveryProctorAssignment[];
  selectedSittingId: string;
  form: ProctorForm;
  editingProctorId: string;
  submitting: boolean;
  message: string | null;
  error: string | null;
  onFormChange: (patch: Partial<ProctorForm>) => void;
  onCreate: (event: FormEvent<HTMLFormElement>) => void;
  onEdit: (assignment: DeliveryProctorAssignment) => void;
  onCancel: (proctorAssignmentId: number) => Promise<void>;
  onNew: () => void;
}) {
  const roomOptions = sittingRooms.map((room) => ({
    value: String(room.exam_sitting_room_id),
    label: `${asString(room.room_code)} - ${asString(room.room_name)}`,
  }));
  const instructorOptions = instructors.map((it) => ({
    value: getId(it, 'user_id') || getId(it, 'account_user_id'),
    label: `${asString(it.instructor_code)} - ${asString(it.full_name)}${it.username ? ` (${asString(it.username)})` : ''}`,
  })).filter((option) => option.value);
  const instructorsWithoutAccounts = instructors.filter((it) => !(getId(it, 'user_id') || getId(it, 'account_user_id'))).length;
  const canAssignProctor = Boolean(selectedSittingId && roomOptions.length > 0 && instructorOptions.length > 0 && form.exam_sitting_room_id && form.proctor_user_id);
  return (
    <>
      <ApiCoverageNotice status="connected">Giám thị dùng API `/delivery/exam-sitting-rooms/{'{id}'}/proctors`.</ApiCoverageNotice>
      {!selectedSittingId ? <p className="muted">Vui lòng chọn hoặc tạo ca thi trước.</p> : null}
      {selectedSittingId && roomOptions.length === 0 ? <p className="muted">Ca thi chưa có phòng thi. Hãy thêm phòng thi trước khi gắn giám thị.</p> : null}
      {selectedSittingId && instructorOptions.length === 0 ? <p className="muted">Chưa có giảng viên nào có tài khoản người dùng để gắn giám thị.</p> : null}
      {instructorsWithoutAccounts > 0 ? <p className="muted">{instructorsWithoutAccounts} giảng viên chưa có tài khoản nên không thể chọn làm giám thị.</p> : null}
      <form className="setup-form" onSubmit={onCreate}>
        <SelectInput id="proctor-room" label="Phòng thi" options={roomOptions} value={form.exam_sitting_room_id} onChange={(v) => onFormChange({ exam_sitting_room_id: v })} disabled={Boolean(editingProctorId)} />
        <SelectInput id="proctor-user" label="Tài khoản giám thị" options={instructorOptions} value={form.proctor_user_id} onChange={(v) => onFormChange({ proctor_user_id: v })} disabled={Boolean(editingProctorId)} />
        <SelectInput
          id="proctor-role"
          label="Giám thị"
          options={[{ label: 'HEAD_PROCTOR', value: 'HEAD_PROCTOR' }, { label: 'ROOM_PROCTOR', value: 'ROOM_PROCTOR' }, { label: 'SUPPORT_STAFF', value: 'SUPPORT_STAFF' }, { label: 'TECH_SUPPORT', value: 'TECH_SUPPORT' }]}
          value={form.proctor_role}
          onChange={(v) => onFormChange({ proctor_role: v })}
        />
        <div className="setup-form-actions">
          <button className="primary-button" type="submit" disabled={submitting || !canAssignProctor}>{editingProctorId ? 'Cập nhật giám thị' : 'Gán giám thị'}</button>
          {editingProctorId ? <button className="ghost-button" type="button" onClick={onNew}>Nhập phân công mới</button> : null}
        </div>
      </form>
      {error ? <p className="form-error">{error}</p> : null}
      {message ? <p className="success-message">{message}</p> : null}
      <SimpleTable
        columns={[['proctor_display_name', 'Giám thị'], ['proctor_role', 'Vai trò'], ['status', 'Trạng thái']]}
        rows={proctors as unknown as ExamSetupRow[]}
        emptyText="Chưa có phân công giám thị."
        actions={(row) => (
          <div className="inline-actions">
            <button type="button" className="ghost-button" onClick={() => onEdit(row as unknown as DeliveryProctorAssignment)}>Sửa</button>
            <button type="button" className="ghost-button" onClick={() => void onCancel(Number(row.proctor_assignment_id))}>Hủy</button>
          </div>
        )}
      />
    </>
  );
}

function SittingClassSectionsPanel({
  allClassSections,
  sittingClassSections,
  classSectionDraft,
  selectedSittingId,
  selectedSitting,
  loading,
  submitting,
  message,
  error,
  onToggle,
  onSave,
  importing,
  onImportStudents,
}: {
  allClassSections: ExamSetupRow[];
  sittingClassSections: SittingClassSection[];
  classSectionDraft: Set<number>;
  selectedSittingId: string;
  selectedSitting: SetupSitting | undefined;
  loading: boolean;
  submitting: boolean;
  message: string | null;
  error: string | null;
  onToggle: (classSectionId: number) => void;
  onSave: () => Promise<void>;
  importing: boolean;
  onImportStudents: () => Promise<void>;
}) {
  const isLocked = sittingVersionIsLocked(selectedSitting);
  const lockedReason = selectedSitting
    ? `Ca thi đang ở trạng thái ${asString(selectedSitting.sitting_status)}; không thể thay đổi lớp học phần.`
    : '';

  const attachedIds = new Set(sittingClassSections.map((r) => r.class_section_id));
  const draftChanged =
    classSectionDraft.size !== attachedIds.size ||
    Array.from(classSectionDraft).some((id) => !attachedIds.has(id));

  return (
    <section className="setup-card setup-card-wide" data-testid="sitting-class-sections-panel">
      <div className="section-heading">
        <div>
          <h3>Lớp học phần tham gia ca thi</h3>
          <p className="muted">
            Lớp học phần chỉ dùng để hỗ trợ lập danh sách dự thi. Danh sách thí sinh chính thức
            của ca thi là <strong>Exam Assignment</strong>.
          </p>
        </div>
      </div>

      {!selectedSittingId ? (
        <p className="muted">Vui lòng chọn hoặc tạo ca thi trước.</p>
      ) : loading ? (
        <p className="muted">Đang tải lớp học phần...</p>
      ) : (
        <>
          {isLocked ? (
            <p className="form-error">{lockedReason}</p>
          ) : null}

          {allClassSections.length === 0 ? (
            <p className="muted">Chưa có lớp học phần trong hệ thống. Hãy tạo lớp học phần trước.</p>
          ) : (
            <div className="setup-checkbox-list" data-testid="class-section-checkbox-list">
              {allClassSections.map((cs) => {
                const id = Number(cs.class_section_id ?? cs.id ?? 0);
                if (!id) return null;
                const checked = classSectionDraft.has(id);
                const wasAttached = attachedIds.has(id);
                return (
                  <label
                    key={id}
                    htmlFor={`class-section-${id}`}
                    className="setup-checkbox-item"
                  >
                    <input
                      id={`class-section-${id}`}
                      type="checkbox"
                      checked={checked}
                      disabled={isLocked || submitting}
                      onChange={() => onToggle(id)}
                    />
                    <span>
                      {asString(cs.class_code)} — {asString(cs.class_name)}
                      {wasAttached ? (
                        <span className="badge badge-active" style={{ marginLeft: '0.4rem' }}>đang gắn</span>
                      ) : null}
                    </span>
                  </label>
                );
              })}
            </div>
          )}

          <div className="setup-form-actions" style={{ marginTop: '1rem' }}>
            <button
              type="button"
              className="primary-button"
              data-testid="class-section-save-btn"
              disabled={isLocked || submitting || !draftChanged}
              title={isLocked ? lockedReason : undefined}
              onClick={() => void onSave()}
            >
              {submitting ? 'Đang lưu...' : 'Lưu lớp học phần'}
            </button>
          </div>

          {error ? <p className="form-error">{error}</p> : null}
          {message ? <p className="success-message">{message}</p> : null}

          <hr style={{ margin: '1.5rem 0', opacity: 0.2 }} />

          <div>
            <h4 style={{ marginBottom: '0.5rem' }}>Nạp sinh viên từ các lớp đã chọn vào ca thi</h4>
            <p className="muted" style={{ marginBottom: '0.75rem' }}>
              Sau khi lưu lớp học phần, bấm nút dưới để nạp toàn bộ sinh viên từ các lớp đã chọn
              vào danh sách Exam Assignment của ca thi này.
            </p>
            <button
              type="button"
              className="ghost-button"
              data-testid="class-section-import-btn"
              disabled={isLocked || submitting || importing || sittingClassSections.length === 0}
              onClick={() => void onImportStudents()}
            >
              {importing ? 'Đang nạp sinh viên...' : 'Nạp sinh viên từ các lớp đã chọn vào ca thi'}
            </button>
          </div>
        </>
      )}
    </section>
  );
}

function AssignmentsPanel({
  students,
  assignments,
  selectedSittingId,
  selectedSitting,
  form,
  importForm,
  editingAssignmentId,
  submitting,
  message,
  error,
  onFormChange,
  onImportFormChange,
  onCreate,
  onImport,
  onEdit,
  onDeactivate,
  onNew,
}: {
  students: ExamSetupRow[];
  assignments: DeliveryExamAssignment[];
  selectedSittingId: string;
  selectedSitting: SetupSitting | undefined;
  form: AssignmentForm;
  importForm: AssignmentImportForm;
  editingAssignmentId: string;
  submitting: boolean;
  message: string | null;
  error: string | null;
  onFormChange: (patch: Partial<AssignmentForm>) => void;
  onImportFormChange: (patch: Partial<AssignmentImportForm>) => void;
  onCreate: (event: FormEvent<HTMLFormElement>) => void;
  onImport: (event: FormEvent<HTMLFormElement>) => void;
  onEdit: (assignment: DeliveryExamAssignment) => void;
  onDeactivate: (assignment: DeliveryExamAssignment) => Promise<void>;
  onNew: () => void;
}) {
  const studentOptions = students.map((it) => ({
    value: getId(it, 'student_id'),
    label: `${asString(it.student_code)} - ${asString(it.full_name)}`,
  }));
  return (
    <>
      <ApiCoverageNotice status="connected">Danh sách thí sinh dùng API `/delivery/exam-sittings/{'{id}'}/assignments`.</ApiCoverageNotice>
      {!selectedSittingId ? <p className="muted">Vui lòng chọn hoặc tạo ca thi trước.</p> : null}
      <p className="muted">
        Sinh viên dự thi được gắn trực tiếp vào ca thi bằng mã sinh viên và mã ca thi; không ràng buộc theo lớp học phần.
      </p>
      <form className="setup-form" onSubmit={onImport}>
        <label htmlFor="assignment-import-rows">
          Nhập danh sách sinh viên dự thi (Import)
          <textarea
            id="assignment-import-rows"
            rows={6}
            placeholder={`Mỗi dòng: mã sinh viên, mã ca thi\nSV001, ${selectedSitting?.sitting_code || 'MA-CA-THI'}\nSV002, ${selectedSitting?.sitting_code || 'MA-CA-THI'}`}
            value={importForm.rows_text}
            onChange={(event) => onImportFormChange({ rows_text: event.target.value })}
          />
        </label>
        <SelectInput
          id="assignment-import-status"
          label="Trạng thái import"
          options={[{ label: 'ASSIGNED', value: 'ASSIGNED' }, { label: 'CHECKED_IN', value: 'CHECKED_IN' }, { label: 'CANCELLED', value: 'CANCELLED' }]}
          value={importForm.assignment_status}
          onChange={(v) => onImportFormChange({ assignment_status: v })}
        />
        <TextInput id="assignment-import-note" label="Ghi chú import" value={importForm.note} onChange={(v) => onImportFormChange({ note: v })} />
        <div className="setup-form-actions">
          <button className="primary-button" type="submit" disabled={submitting || !selectedSittingId || !importForm.rows_text.trim()}>
            Nhập danh sách sinh viên vào ca thi
          </button>
        </div>
      </form>
      <form className="setup-form" onSubmit={onCreate}>
        <SelectInput id="assignment-student" label="Danh sách thí sinh" options={studentOptions} value={form.student_id} onChange={(v) => onFormChange({ student_id: v })} disabled={Boolean(editingAssignmentId)} />
        <SelectInput id="assignment-status" label="Trạng thái" options={[{ label: 'ASSIGNED', value: 'ASSIGNED' }, { label: 'CHECKED_IN', value: 'CHECKED_IN' }, { label: 'CANCELLED', value: 'CANCELLED' }]} value={form.assignment_status} onChange={(v) => onFormChange({ assignment_status: v })} />
        <TextInput id="assignment-note" label="Ghi chú" value={form.note} onChange={(v) => onFormChange({ note: v })} />
        <div className="setup-form-actions">
          <button className="primary-button" type="submit" disabled={submitting || !selectedSittingId}>{editingAssignmentId ? 'Cập nhật thí sinh' : 'Thêm thí sinh'}</button>
          {editingAssignmentId ? <button className="ghost-button" type="button" onClick={onNew}>Nhập thí sinh mới</button> : null}
        </div>
      </form>
      {error ? <p className="form-error">{error}</p> : null}
      {message ? <p className="success-message">{message}</p> : null}
      <SimpleTable
        columns={[['student_code', 'Mã SV'], ['student_name', 'Họ tên'], ['assignment_status', 'Trạng thái'], ['note', 'Ghi chú']]}
        rows={assignments as unknown as ExamSetupRow[]}
        emptyText="Chưa có thí sinh."
        actions={(row) => (
          <div className="inline-actions">
            <button type="button" className="ghost-button" onClick={() => onEdit(row as unknown as DeliveryExamAssignment)}>Sửa</button>
            <button type="button" className="ghost-button" onClick={() => void onDeactivate(row as unknown as DeliveryExamAssignment)}>Hủy</button>
          </div>
        )}
      />
    </>
  );
}

function SeatingPanel({
  stations,
  sittingRooms,
  assignments,
  seating,
  selectedSittingId,
  form,
  editingStationAssignmentId,
  submitting,
  message,
  error,
  onFormChange,
  onCreate,
  onAutoAssign,
  onEdit,
  onDeactivate,
  onNew,
  stationLoading,
}: {
  stations: ExamSetupRow[];
  sittingRooms: DeliverySittingRoom[];
  assignments: DeliveryExamAssignment[];
  seating: DeliveryStationAssignment[];
  selectedSittingId: string;
  form: StationAssignmentForm;
  editingStationAssignmentId: string;
  submitting: boolean;
  message: string | null;
  error: string | null;
  onFormChange: (patch: Partial<StationAssignmentForm>) => void;
  onCreate: (event: FormEvent<HTMLFormElement>) => void;
  onAutoAssign: () => Promise<void>;
  onEdit: (assignment: DeliveryStationAssignment) => void;
  onDeactivate: (assignment: DeliveryStationAssignment) => Promise<void>;
  onNew: () => void;
  stationLoading: boolean;
}) {
  const sortedStations = useMemo(() => sortByStationCode(stations as Array<{ station_code?: string | null }>) as ExamSetupRow[], [stations]);
  const roomOptions = sittingRooms.map((it) => ({ value: String(it.exam_sitting_room_id), label: `${asString(it.room_code)} - ${asString(it.room_name)}` }));
  const selectedSittingRoom = sittingRooms.find((room) => String(room.exam_sitting_room_id) === form.exam_sitting_room_id);
  const filteredStations = selectedSittingRoom
    ? sortedStations.filter((it) => {
        const stationRoomId = it.room_id == null ? '' : String(it.room_id);
        const stationRoomCode = String(it.room_code || '');
        return !stationRoomId || stationRoomId === String(selectedSittingRoom.room_id) || stationRoomCode === String(selectedSittingRoom.room_code || '');
      })
    : [];
  const occupiedAssignmentIds = new Set(seating.map((it) => String(it.exam_assignment_id)));
  const occupiedStationIds = new Set(seating.map((it) => String(it.station_id)));
  const stationOptions = filteredStations
    .filter((it) => editingStationAssignmentId || !occupiedStationIds.has(getId(it, 'station_id')))
    .map((it) => ({ value: getId(it, 'station_id'), label: `${asString(it.room_code)} - ${asString(it.station_code)}` }));
  const assignmentOptions = assignments.map((it) => ({ value: String(it.exam_assignment_id), label: `${asString(it.student_code)} - ${asString(it.student_name)}` }));
  const unassignedCount = assignments.filter((it) => !occupiedAssignmentIds.has(String(it.exam_assignment_id))).length;
  const sortedSeating = useMemo(() => sortByStationCode(seating as Array<{ station_code?: string | null }>), [seating]);
  const canAssignSeat = Boolean(
    selectedSittingId &&
    form.exam_assignment_id &&
    form.exam_sitting_room_id &&
    form.station_id &&
    roomOptions.length > 0 &&
    assignmentOptions.length > 0 &&
    stationOptions.length > 0 &&
    !stationLoading
  );
  const canAutoAssign = Boolean(selectedSittingId && form.exam_sitting_room_id && unassignedCount > 0 && stationOptions.length > 0 && !editingStationAssignmentId && !stationLoading);

  return (
    <>
      <ApiCoverageNotice status="connected">Sơ đồ chỗ ngồi dùng API `/delivery/exam-sittings/{'{id}'}/seating-plan`.</ApiCoverageNotice>
      {!selectedSittingId ? <p className="muted">Vui lòng chọn hoặc tạo ca thi trước.</p> : null}
      {selectedSittingId && assignmentOptions.length === 0 ? <p className="muted">Ca thi chưa có sinh viên dự thi. Hãy nhập danh sách sinh viên trước khi xếp máy.</p> : null}
      {selectedSittingId && roomOptions.length === 0 ? <p className="muted">Ca thi chưa có phòng thi. Hãy thêm phòng thi trước khi xếp máy.</p> : null}
      <form className="setup-form" onSubmit={onCreate}>
        <SelectInput id="seat-assignment" label="Danh sách thí sinh" options={assignmentOptions} value={form.exam_assignment_id} onChange={(v) => onFormChange({ exam_assignment_id: v })} disabled={Boolean(editingStationAssignmentId)} />
        <SelectInput id="seat-room" label="Phòng thi trong ca" options={roomOptions} value={form.exam_sitting_room_id} onChange={(v) => onFormChange({ exam_sitting_room_id: v, station_id: '' })} disabled={Boolean(editingStationAssignmentId)} />
        <SelectInput id="seat-station" label="Vị trí máy" options={stationOptions} value={form.station_id} onChange={(v) => onFormChange({ station_id: v })} />
        <TextInput id="seat-device" label="Thiết bị dự kiến" type="number" value={form.planned_device_id} onChange={(v) => onFormChange({ planned_device_id: v })} />
        {form.exam_sitting_room_id && stationLoading ? <p className="muted">Đang tải máy của phòng thi đã chọn...</p> : null}
        {form.exam_sitting_room_id && !stationLoading && stationOptions.length === 0 ? <p className="muted">Phòng thi trong ca đã chọn chưa có máy trống trong danh mục phòng. Kiểm tra danh mục máy của phòng này.</p> : null}
        <div className="setup-form-actions">
          <button className="primary-button" type="submit" disabled={submitting || !canAssignSeat}>{editingStationAssignmentId ? 'Cập nhật chỗ ngồi' : 'Gán chỗ'}</button>
          <button className="secondary-button" type="button" disabled={submitting || !canAutoAssign} onClick={() => void onAutoAssign()}>
            Gán tự động
          </button>
          {editingStationAssignmentId ? <button className="ghost-button" type="button" onClick={onNew}>Nhập chỗ mới</button> : null}
        </div>
      </form>
      {error ? <p className="form-error">{error}</p> : null}
      {message ? <p className="success-message">{message}</p> : null}
      <SimpleTable
        columns={[['station_code', 'Vị trí máy'], ['student_code', 'Mã SV'], ['student_name', 'Họ tên'], ['planned_device_asset_tag', 'Thiết bị dự kiến'], ['status', 'Trạng thái']]}
        rows={sortedSeating as unknown as ExamSetupRow[]}
        emptyText="Chưa có dữ liệu sơ đồ chỗ ngồi."
        actions={(row) => (
          <div className="inline-actions">
            <button type="button" className="ghost-button" onClick={() => onEdit(row as unknown as DeliveryStationAssignment)}>Sửa</button>
            <button type="button" className="ghost-button" onClick={() => void onDeactivate(row as unknown as DeliveryStationAssignment)}>Hủy</button>
          </div>
        )}
      />
      <button type="button" className="ghost-button" disabled>Khóa sơ đồ chỗ ngồi</button>
    </>
  );
}

function SittingVersionPanel({
  versions,
  selectedSitting,
  appliedExamVersionId,
  appliedVersion,
  submitting,
  message,
  error,
  onAssign,
}: {
  versions: ExamSetupRow[];
  selectedSitting: SetupSitting | undefined;
  appliedExamVersionId: string;
  appliedVersion: ExamSetupRow | undefined;
  submitting: boolean;
  message: string | null;
  error: string | null;
  onAssign: (examVersionId: string) => Promise<void>;
}) {
  const [candidateVersionId, setCandidateVersionId] = useState(appliedExamVersionId);
  const isLocked = sittingVersionIsLocked(selectedSitting);
  const lockedMessage = `Ca thi đang ở trạng thái ${asString(selectedSitting?.sitting_status)} nên không thể đổi phiên bản đề áp dụng. Hãy gắn phiên bản khi ca thi còn DRAFT hoặc tạo ca thi mới.`;

  const versionOptions = useMemo(() => {
    const mapped = versions
      .map((version) => {
        const value = getExamVersionId(version);
        return {
          value,
          label: formatExamVersionOptionLabel(version, value),
        };
      })
      .filter((option) => option.value);

    if (appliedExamVersionId && !mapped.some((option) => option.value === appliedExamVersionId)) {
      mapped.unshift({
        value: appliedExamVersionId,
        label: formatExamVersionOptionLabel(
          {
            exam_code: selectedSitting?.exam_code,
            version_label: selectedSitting?.exam_version_label,
            status: selectedSitting?.exam_version_status,
          },
          appliedExamVersionId
        ),
      });
    }

    return mapped;
  }, [versions, appliedExamVersionId, selectedSitting]);
  const versionOptionIds = useMemo(() => new Set(versionOptions.map((option) => option.value)), [versionOptions]);
  const appliedVersionIsInOptions = Boolean(appliedExamVersionId && versionOptionIds.has(appliedExamVersionId));
  const candidateSelectValue = candidateVersionId && versionOptionIds.has(candidateVersionId) ? candidateVersionId : '';
  const canAssignCandidate = Boolean(candidateSelectValue && candidateSelectValue !== appliedExamVersionId && !submitting && !isLocked);
  const lockedAssignReason = `Ca thi ${asString(selectedSitting?.sitting_code)} đang ở trạng thái ${asString(
    selectedSitting?.sitting_status
  )}; chỉ được gắn/đổi phiên bản đề khi ca thi còn DRAFT.`;

  function getAssignDisabledReason(isApplied: boolean): string | null {
    if (submitting) return 'Đang lưu thay đổi.';
    if (isLocked) return lockedAssignReason;
    if (isApplied) return 'Phiên bản này đang được áp dụng cho ca thi.';
    return null;
  }

  useEffect(() => {
    setCandidateVersionId(appliedVersionIsInOptions ? appliedExamVersionId : '');
  }, [appliedExamVersionId, appliedVersionIsInOptions]);

  if (!selectedSitting) {
    return <p className="muted">Vui lòng chọn hoặc tạo ca thi trước.</p>;
  }

  return (
    <section className="setup-card setup-card-wide">
      <div className="section-heading">
        <div>
          <h3>Gắn phiên bản đề cho ca thi</h3>
          <p className="muted">Sau khi chọn ca thi, appliedExamVersionId được lấy từ sitting.exam_version_id và là nguồn sự thật duy nhất.</p>
        </div>
      </div>
      <div className="setup-status-note">
        <strong>Phiên bản đề áp dụng:</strong>
        <span>
          {' '}
          {appliedExamVersionId
            ? `${asString(appliedVersion?.version_label, asString(selectedSitting.exam_version_label, `ID ${appliedExamVersionId}`))}`
            : 'Ca thi chưa gắn phiên bản đề. Vui lòng chọn phiên bản đề áp dụng.'}
        </span>
      </div>
      {isLocked ? <p className="form-error">{lockedMessage}</p> : null}
      {appliedExamVersionId && !appliedVersionIsInOptions ? (
        <p className="setup-warning">
          Phiên bản đang gắn với ca thi không nằm trong danh sách phiên bản đang hiển thị. Hãy chọn lại phiên bản đề áp dụng từ danh sách bên dưới.
        </p>
      ) : null}
      <div className="setup-form setup-form-single">
        <SelectInput
          id="applied-version-selector"
          label="Phiên bản đề áp dụng"
          options={versionOptions.length > 0 ? versionOptions : [{ label: 'Chưa có phiên bản đề', value: '' }]}
          value={candidateSelectValue}
          onChange={setCandidateVersionId}
          disabled={isLocked}
        />
        <div className="setup-form-actions">
          <button
            className="primary-button"
            type="button"
            disabled={!canAssignCandidate}
            onClick={() => void onAssign(candidateSelectValue)}
          >
            Gắn phiên bản đề cho ca thi
          </button>
        </div>
      </div>
      <div className="master-data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Phiên bản đề</th>
              <th>Trạng thái</th>
              <th>Hành động</th>
            </tr>
          </thead>
          <tbody>
            {versionOptions.length === 0 ? (
              <tr>
                <td colSpan={3}>Chưa có phiên bản đề để gắn cho ca thi.</td>
              </tr>
            ) : (
              versionOptions.map((option) => {
                const isApplied = option.value === appliedExamVersionId;
                const isCandidate = option.value === candidateSelectValue;
                const disabledReason = getAssignDisabledReason(isApplied);
                return (
                  <tr key={option.value}>
                    <td>{option.label}</td>
                    <td>{disabledReason || (isCandidate ? 'Đang chọn' : 'Có thể gắn')}</td>
                    <td>
                      <div className="inline-actions">
                        <button type="button" className="ghost-button" disabled={isLocked} title={isLocked ? lockedAssignReason : undefined} onClick={() => setCandidateVersionId(option.value)}>
                          Chọn
                        </button>
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={Boolean(disabledReason)}
                          title={disabledReason || `Gắn ${option.label} cho ca thi ${asString(selectedSitting?.sitting_code)}`}
                          onClick={() => void onAssign(option.value)}
                        >
                          {isApplied ? 'Đã gắn' : isLocked ? 'Bị khóa' : 'Gắn phiên bản này'}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      {error ? <p className="form-error">{error}</p> : null}
      {message ? <p className="success-message">{message}</p> : null}
    </section>
  );
}

function SittingReadinessPanel({
  selectedSitting,
  sittingReadiness,
  sittingReadinessLoading,
  sittingReadinessError,
  sittingReadinessStale,
  onSelect,
  onRefresh,
}: {
  selectedSitting: SetupSitting | undefined;
  sittingReadiness: SittingReadiness | null;
  sittingReadinessLoading: boolean;
  sittingReadinessError: string | null;
  sittingReadinessStale: boolean;
  onSelect: (key: SetupSectionKey) => void;
  onRefresh: () => Promise<void>;
}) {
  const blockers = sittingReadiness?.blockers ?? [];
  const warnings = sittingReadiness?.warnings ?? [];
  const ready = Boolean(sittingReadiness?.ready);

  return (
    <section className="setup-card setup-card-wide" data-testid="sitting-readiness-section">
      <div className="section-heading">
        <div>
          <h3>Kiểm tra readiness</h3>
          <p className="muted">Readiness chỉ kiểm tra cấu hình, không thay thế bước nhập liệu.</p>
        </div>
        <StatusBadge value={ready ? 'READY_CHECK_PASSED' : selectedSitting ? 'READY_CHECK_FAILED' : 'NO_SITTING'} />
      </div>
      <div className="setup-form-actions">
        <IconActionButton
          icon="refresh"
          variant="ghost-button"
          label={sittingReadinessError ? 'Thử lại readiness' : 'Tải lại readiness'}
          disabled={!selectedSitting || sittingReadinessLoading}
          onClick={() => void onRefresh()}
        />
        {sittingReadinessStale ? <span className="muted">Readiness có thể đã cũ. Hãy tải lại trước khi phát hành.</span> : null}
      </div>
      {!selectedSitting ? <p className="muted">Vui lòng chọn hoặc tạo ca thi trước.</p> : null}
      {sittingReadinessLoading ? <p className="muted">Đang tải readiness từ API...</p> : null}
      {sittingReadinessError ? <p className="form-error">{sittingReadinessError}</p> : null}
      {selectedSitting && sittingReadiness ? (
        <div className="setup-overview-grid">
          <div className="stat-tile">
            <span>Trạng thái backend</span>
            <p>{ready ? 'Backend xác nhận ca thi đã đủ điều kiện mở.' : 'Backend còn blocker cần xử lý trước khi mở ca thi.'}</p>
          </div>
          <div className="stat-tile">
            <span>Tổng hợp cấu hình</span>
            <p>
              Sinh viên: {sittingReadiness.counts.assignment_count} · Phòng: {sittingReadiness.counts.room_count} · Xếp máy:{' '}
              {sittingReadiness.counts.station_assignment_count} · Giám thị: {sittingReadiness.counts.proctor_count}
            </p>
          </div>
          {sittingReadiness.summary ? (
            <div className="stat-tile">
              <span>Backend summary</span>
              <p>{sittingReadiness.summary}</p>
            </div>
          ) : null}
          {(typeof sittingReadiness.can_prepare === 'boolean' || typeof sittingReadiness.can_open === 'boolean') ? (
            <div className="stat-tile">
              <span>Điều khiển backend</span>
              <p>
                Prepare: {typeof sittingReadiness.can_prepare === 'boolean' ? (sittingReadiness.can_prepare ? 'có thể' : 'chưa thể') : 'không cung cấp'} · Open:{' '}
                {typeof sittingReadiness.can_open === 'boolean' ? (sittingReadiness.can_open ? 'có thể' : 'chưa thể') : 'không cung cấp'}
              </p>
            </div>
          ) : null}
        </div>
      ) : null}
      <div className="master-data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Mã kiểm tra</th>
              <th>Mức độ</th>
              <th>Thông điệp</th>
              <th>Đi tới</th>
            </tr>
          </thead>
          <tbody>
            {!selectedSitting || !sittingReadiness ? (
              <tr>
                <td colSpan={4}>Chưa có dữ liệu.</td>
              </tr>
            ) : blockers.length === 0 ? (
              <tr>
                <td>ready</td>
                <td>OK</td>
                <td>Không có blocker từ backend.</td>
                <td><span className="muted">-</span></td>
              </tr>
            ) : (
              blockers.map((issue) => {
                const target = readinessTargetForCode(issue.code);
                return (
                  <tr key={`${issue.code}-${issue.message}`}>
                    <td>{asString(issue.code, 'unknown')}</td>
                    <td>{asString(issue.severity, asString(issue.status, 'ERROR'))}</td>
                    <td>{asString(issue.message, 'Thiếu dữ liệu readiness')}</td>
                    <td>
                      {target ? (
                        <button type="button" className="ghost-button" onClick={() => onSelect(target)}>
                          Sửa cấu hình
                        </button>
                      ) : (
                        <span className="muted">-</span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      {warnings.length > 0 ? (
        <ul className="setup-inline-notes">
          {warnings.map((item, index) => (
            <li key={`sitting-readiness-warning-${index}`}>{asString(item.code, asString(item.message, 'warning'))}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function PublishPanel({
  sittings,
  selectedSittingId,
  selectedSitting,
  sittingReadiness,
  sittingReadinessLoading,
  sittingReadinessError,
  sittingReadinessStale,
  submitting,
  message,
  error,
  onSelect,
  onSelectSitting,
  onPrepare,
  onChangeStatus,
  onRefreshReadiness,
}: {
  sittings: SetupSitting[];
  selectedSittingId: string;
  selectedSitting: SetupSitting | undefined;
  sittingReadiness: SittingReadiness | null;
  sittingReadinessLoading: boolean;
  sittingReadinessError: string | null;
  sittingReadinessStale: boolean;
  submitting: boolean;
  message: string | null;
  error: string | null;
  onSelect: (key: SetupSectionKey) => void;
  onSelectSitting: (value: string) => void;
  onPrepare: () => Promise<void>;
  onChangeStatus: (status: string) => Promise<void>;
  onRefreshReadiness: () => Promise<void>;
}) {
  const blockers = sittingReadiness?.blockers ?? [];
  const ready = Boolean(sittingReadiness?.ready);
  const status = String(selectedSitting?.sitting_status || '').toUpperCase();
  const canPrepare = !sittingReadinessLoading && ready && status === 'DRAFT';
  const canPrepareRuntime = !sittingReadinessLoading && (typeof sittingReadiness?.can_prepare === 'boolean'
    ? sittingReadiness.can_prepare
    : ready && ['READY', 'OPEN', 'IN_PROGRESS'].includes(status));
  const canOpen = !sittingReadinessLoading && (typeof sittingReadiness?.can_open === 'boolean'
    ? sittingReadiness.can_open
    : ready && status === 'READY');
  const actionGateLabel = typeof sittingReadiness?.can_prepare === 'boolean' || typeof sittingReadiness?.can_open === 'boolean'
    ? 'Theo cờ backend readiness.'
    : 'Backend chưa trả về cờ action; đang dùng fallback từ readiness + trạng thái ca thi.';

  return (
    <section className="setup-card setup-card-wide" data-testid="publish-open-section">
      <div className="section-heading">
        <div>
          <h3>Publish / Open</h3>
          <p className="muted">Chỉ mở ca thi sau khi readiness đạt. Các tác vụ nặng vẫn chạy qua dịch vụ nền, không chạy trong frontend.</p>
        </div>
        <StatusBadge value={status || 'NO_SITTING'} />
      </div>
      {!selectedSitting ? <p className="muted">Vui lòng chọn hoặc tạo ca thi trước.</p> : null}
      <div className="setup-form-grid">
        <SelectInput
          id="publish-sitting-selector"
          label="Ca thi cần publish/open"
          options={sittings.map((sitting) => ({
            label: `${asString(sitting.sitting_code)} - ${asString(sitting.sitting_name)} · ${asString(sitting.sitting_status)}`,
            value: String(sitting.exam_sitting_id),
          }))}
          value={selectedSittingId}
          onChange={onSelectSitting}
          placeholder="Chọn ca thi cần thao tác"
        />
      </div>
      {sittings.length > 1 ? (
        <div className="table-wrapper">
          <table className="setup-table">
            <thead>
              <tr>
                <th>Ca thi</th>
                <th>Phiên bản đề</th>
                <th>Trạng thái</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {sittings.map((sitting) => {
                const rowId = String(sitting.exam_sitting_id);
                return (
                  <tr key={rowId}>
                    <td>{asString(sitting.sitting_code)} - {asString(sitting.sitting_name)}</td>
                    <td>{asString(sitting.exam_version_label, sitting.exam_version_id ? `ID ${sitting.exam_version_id}` : '-')}</td>
                    <td><StatusBadge value={rowId === selectedSittingId ? status || asString(sitting.sitting_status) : asString(sitting.sitting_status)} /></td>
                    <td>
                      <button type="button" className="ghost-button" disabled={rowId === selectedSittingId} onClick={() => onSelectSitting(rowId)}>
                        Chọn ca này
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
      <div className="setup-status-note">
        <strong>Trạng thái hiện tại:</strong>
        <span> {status || '-'}</span>
      </div>
      <div className="setup-status-note">
        <strong>Readiness:</strong>
        <span>
          {' '}
          {sittingReadinessLoading
            ? 'Đang tải readiness từ API.'
            : ready
              ? 'Đạt, có thể chuyển trạng thái.'
              : 'Chưa đạt, cần xử lý blocker từ backend trước khi mở ca thi.'}
        </span>
      </div>
      <div className="setup-status-note">
        <strong>Điều kiện thao tác:</strong>
        <span> {actionGateLabel}</span>
      </div>
      <div className="setup-form-actions">
        <button type="button" className="ghost-button" disabled={!selectedSitting || sittingReadinessLoading || submitting} onClick={() => void onRefreshReadiness()}>
          {sittingReadinessError ? 'Thử lại readiness' : 'Làm mới readiness'}
        </button>
        {sittingReadinessStale ? <span className="muted">Readiness có thể đã cũ sau khi thay đổi cấu hình.</span> : null}
      </div>
      {!ready && blockers.length > 0 ? (
        <ul className="setup-inline-notes">
          {blockers.map((issue) => {
            const target = readinessTargetForCode(issue.code);
            return (
              <li key={`${issue.code}-${issue.message}`}>
                {asString(issue.message, asString(issue.code, 'Thiếu dữ liệu readiness'))}{' '}
                {target ? (
                  <button type="button" className="ghost-button" onClick={() => onSelect(target)}>
                    Sửa cấu hình
                  </button>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
      <div className="setup-form-actions">
        <button className="primary-button" type="button" disabled={submitting || !canPrepare} onClick={() => void onChangeStatus('READY')}>
          Đánh dấu READY
        </button>
        <button className="secondary-button" type="button" disabled={submitting || !canPrepareRuntime} onClick={() => void onPrepare()}>
          Chuẩn bị runtime
        </button>
        <button className="secondary-button" type="button" disabled={submitting || !canOpen} onClick={() => void onChangeStatus('OPEN')}>
          Mở ca thi
        </button>
      </div>
      {status === 'OPEN' || status === 'IN_PROGRESS' ? <p className="success-message">Ca thi đã mở. Dashboard sinh viên chỉ hiển thị khi runtime đã có exam_session cho sinh viên.</p> : null}
      {status === 'DRAFT' && ready ? <p className="muted">Bước tiếp theo: bấm “Đánh dấu READY”, bấm “Chuẩn bị runtime”, sau đó bấm “Mở ca thi”.</p> : null}
      {status === 'READY' && ready ? <p className="muted">Bước tiếp theo: bấm “Chuẩn bị runtime”, sau đó bấm “Mở ca thi”.</p> : null}
      {selectedSitting && !sittingReadinessLoading && !sittingReadiness && !sittingReadinessError ? (
        <p className="muted">Chưa có dữ liệu readiness từ backend. Không dùng dữ liệu cục bộ để quyết định publish/open.</p>
      ) : null}
      {error ? <p className="form-error">{error}</p> : null}
      {message ? <p className="success-message">{message}</p> : null}
    </section>
  );
}

function OperationsPanel({ modules }: { modules: ModuleStatus[] }) {
  return (
    <>
      <ApiCoverageNotice status="connected">
        Trạng thái vận hành hiển thị theo các status API đang có. Không hiển thị heartbeat giả cho tiến trình nền.
      </ApiCoverageNotice>
      <div className="setup-kpi-grid">
        {modules.map((module) => (
          <div className="stat-tile" key={module.endpoint}>
            <span>{module.ready ? 'OK' : 'ERR'}</span>
            <p>
              {module.module} · {module.status}
            </p>
          </div>
        ))}
      </div>
    </>
  );
}

function SimpleTable({
  columns,
  rows,
  emptyText = 'Chưa có dữ liệu.',
  actions,
}: {
  columns: Array<[string, string]>;
  rows: ExamSetupRow[];
  emptyText?: string;
  actions?: (row: ExamSetupRow) => ReactNode;
}) {
  return (
    <div className="master-data-table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map(([key, label]) => (
              <th key={key}>{label}</th>
            ))}
            {actions ? <th>Thao tác</th> : null}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={Math.max(columns.length + (actions ? 1 : 0), 1)}>{emptyText}</td>
            </tr>
          ) : (
            rows.map((row, index) => (
              <tr key={asString(row.id ?? row.exam_id ?? row.station_assignment_id ?? row.proctor_assignment_id ?? row.exam_assignment_id ?? row.exam_sitting_room_id ?? row.room_id ?? row.station_id ?? row.student_id ?? row.instructor_id ?? index)}>
                {columns.map(([key]) => (
                  <td key={key}>{key === 'status' || key.endsWith('_status') ? <StatusBadge value={asString(row[key])} /> : asString(row[key])}</td>
                ))}
                {actions ? <td>{actions(row)}</td> : null}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function WorkflowContextPanel({
  selectedSitting,
  appliedExamVersionId,
  appliedVersion,
  versionQuestions,
  questionReadiness,
  sittingRooms,
  assignments,
  seatingPlan,
  proctors,
}: {
  selectedSitting: SetupSitting | undefined;
  appliedExamVersionId: string;
  appliedVersion: ExamSetupRow | undefined;
  versionQuestions: ExamVersionQuestionAuthoringItem[];
  questionReadiness: { ready: boolean; missing_items: Array<Record<string, unknown>> };
  sittingRooms: DeliverySittingRoom[];
  assignments: DeliveryExamAssignment[];
  seatingPlan: DeliveryStationAssignment[];
  proctors: DeliveryProctorAssignment[];
}) {
  const hasSitting = Boolean(selectedSitting);
  const hasVersion = Boolean(appliedExamVersionId);
  return (
    <section className="setup-card setup-card-wide" data-testid="workflow-context-panel">
      <div className="section-heading">
        <div>
          <h3>Ca thi đang cấu hình</h3>
          <p className="muted">
            {hasSitting
              ? `${selectedSitting?.sitting_code} - ${selectedSitting?.sitting_name} · ${selectedSitting?.sitting_status}`
              : 'Vui lòng chọn hoặc tạo ca thi trước.'}
          </p>
        </div>
        <StatusBadge value={hasSitting ? asString(selectedSitting?.sitting_status, 'DRAFT') : 'NO_SITTING'} />
      </div>
      <div className="setup-overview-grid">
        <div className="stat-tile">
          <span>Phiên bản đề áp dụng</span>
          <p>
            {hasVersion
              ? `${asString(appliedVersion?.version_label, asString(selectedSitting?.exam_version_label, `ID ${appliedExamVersionId}`))} · ${asString(appliedVersion?.status)}`
              : 'Ca thi chưa gắn phiên bản đề. Vui lòng chọn phiên bản đề áp dụng.'}
          </p>
        </div>
        <div className="stat-tile">
          <span>Tóm tắt cấu hình</span>
          <p>
            Phiên bản đề: {questionReadiness.ready ? 'đã có cấu hình câu hỏi' : 'cần hoàn thiện cấu hình câu hỏi'} · Câu hỏi:{' '}
            {versionQuestions.length} · Sinh viên: {assignments.length} · Phòng: {sittingRooms.length} · Xếp máy: {seatingPlan.length} · Giám thị:{' '}
            {proctors.length}
          </p>
        </div>
      </div>
    </section>
  );
}

function readinessTargetForCode(code: string): SetupSectionKey | null {
  const normalized = String(code || '').trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  if (normalized.includes('assignment') || normalized.includes('student')) {
    return 'assignments';
  }
  if (normalized.includes('station') || normalized.includes('seat')) {
    return 'seating';
  }
  if (normalized.includes('room')) {
    return 'rooms';
  }
  if (normalized.includes('proctor')) {
    return 'proctors';
  }
  if (
    normalized.includes('exam_version') ||
    normalized.includes('question') ||
    normalized.includes('grading') ||
    normalized.includes('capture') ||
    normalized.includes('paper') ||
    normalized.includes('randomization')
  ) {
    return 'sitting-version';
  }
  return null;
}

function renderSection(
  key: SetupSectionKey,
  snapshot: ApiSnapshot,
  handlers: {
    onSelect: (key: SetupSectionKey) => void;
    selectedExamId: string;
    selectedExamVersionId: string;
    examForm: ExamForm;
    examSubmitting: boolean;
    examMessage: string | null;
    examError: string | null;
    versionForm: VersionForm;
    versionSubmitting: boolean;
    versionMessage: string | null;
    versionError: string | null;
    versionPublishing: boolean;
    versionPublishMessage: string | null;
    versionPublishError: string | null;
    versionPublishBlockers: PublishValidationBlocker[];
    examActivationLoading: boolean;
    paperAssets: ExamVersionPaperAsset[];
    paperAssetsLoading: boolean;
    paperSubmitting: boolean;
    paperMessage: string | null;
    paperError: string | null;
    deliveryProfile: ExamVersionDeliveryProfile | null;
    deliveryContentType: DeliveryContentType | '';
    gradingProfiles: QuestionGradingProfileSummary[];
    profileLoading: boolean;
    profileSubmitting: boolean;
    profileMessage: string | null;
    profileError: string | null;
    versionQuestions: ExamVersionQuestionAuthoringItem[];
    questionReadiness: { ready: boolean; missing_items: Array<Record<string, unknown>> };
    questionForm: VersionQuestionForm;
    questionSubmitting: boolean;
    questionMessage: string | null;
    questionError: string | null;
    sittings: SetupSitting[];
    selectedSittingId: string;
    selectedSitting: SetupSitting | undefined;
    appliedExamVersionId: string;
    appliedVersion: ExamSetupRow | undefined;
    appliedVersionQuestions: ExamVersionQuestionAuthoringItem[];
    appliedQuestionReadiness: { ready: boolean; missing_items: Array<Record<string, unknown>> };
    sittingReadiness: SittingReadiness | null;
    sittingReadinessLoading: boolean;
    sittingReadinessError: string | null;
    sittingReadinessStale: boolean;
    sittingRooms: DeliverySittingRoom[];
    proctors: DeliveryProctorAssignment[];
    assignments: DeliveryExamAssignment[];
    seatingPlan: DeliveryStationAssignment[];
    selectedRoomStations: ExamSetupRow[];
    selectedRoomStationsLoading: boolean;
    sittingForm: SittingForm;
    sittingRoomForm: SittingRoomForm;
    proctorForm: ProctorForm;
    assignmentForm: AssignmentForm;
    assignmentImportForm: AssignmentImportForm;
    stationAssignmentForm: StationAssignmentForm;
    editingSittingRoomId: string;
    editingProctorId: string;
    editingAssignmentId: string;
    editingStationAssignmentId: string;
    sittingSubmitting: boolean;
    sittingMessage: string | null;
    sittingError: string | null;
    roomSubmitting: boolean;
    roomMessage: string | null;
    roomError: string | null;
    proctorSubmitting: boolean;
    proctorMessage: string | null;
    proctorError: string | null;
    assignmentSubmitting: boolean;
    assignmentMessage: string | null;
    assignmentError: string | null;
    seatingSubmitting: boolean;
    seatingMessage: string | null;
    seatingError: string | null;
    publishSubmitting: boolean;
    publishMessage: string | null;
    publishError: string | null;
    sittingClassSections: SittingClassSection[];
    classSectionDraft: Set<number>;
    classSectionLoading: boolean;
    classSectionSubmitting: boolean;
    classSectionMessage: string | null;
    classSectionError: string | null;
    onClassSectionToggle: (classSectionId: number) => void;
    onClassSectionSave: () => Promise<void>;
    classSectionImporting: boolean;
    onClassSectionImport: () => Promise<void>;
    onSelectExam: (value: string) => void;
    onSelectExamVersion: (value: string) => void;
    onExamFormChange: (patch: Partial<ExamForm>) => void;
    onExamSubmit: (event: FormEvent<HTMLFormElement>) => void;
    onVersionFormChange: (patch: Partial<VersionForm>) => void;
    onVersionSubmit: (event: FormEvent<HTMLFormElement>) => void;
    onPublishVersion: () => Promise<void>;
    onActivateExamBlueprint: () => Promise<void>;
    onUploadPaperAsset: (file: File) => Promise<void>;
    onRetirePaperAsset: (paperAssetId: number) => Promise<void>;
    onDeliveryContentTypeChange: (value: DeliveryContentType | '') => void;
    onSaveDeliveryContentType: () => Promise<void>;
    onConfigureFileUploadManualGrading: () => Promise<void>;
    onApplyFileUploadPreset: () => Promise<void>;
    onCreatePlaceholderQuestion: () => Promise<void>;
    onRetireGradingProfile: (questionGradingProfileId: number) => Promise<void>;
    onQuestionFormChange: (patch: Partial<VersionQuestionForm>) => void;
    onQuestionTypeChange: (questionType: VersionQuestionForm['question_type']) => void;
    onQuestionSubmit: (event: FormEvent<HTMLFormElement>) => void;
    onQuestionSaveDraft: (draft: VersionQuestionForm) => Promise<QuestionDraftSaveResult>;
    onQuestionEdit: (item: ExamVersionQuestionAuthoringItem) => void;
    onSittingFormChange: (patch: Partial<SittingForm>) => void;
    onSittingSubmit: (event: FormEvent<HTMLFormElement>) => void;
    onSittingSelect: (value: string) => void;
    onNewSitting: () => void;
    onAssignSittingExamVersion: (examVersionId: string) => Promise<void>;
    onSittingRoomFormChange: (patch: Partial<SittingRoomForm>) => void;
    onSittingRoomCreate: (event: FormEvent<HTMLFormElement>) => void;
    onSittingRoomEdit: (room: DeliverySittingRoom) => void;
    onSittingRoomCancel: (examSittingRoomId: number) => Promise<void>;
    onNewSittingRoom: () => void;
    onProctorFormChange: (patch: Partial<ProctorForm>) => void;
    onProctorCreate: (event: FormEvent<HTMLFormElement>) => void;
    onProctorEdit: (assignment: DeliveryProctorAssignment) => void;
    onProctorCancel: (proctorAssignmentId: number) => Promise<void>;
    onNewProctor: () => void;
    onAssignmentFormChange: (patch: Partial<AssignmentForm>) => void;
    onAssignmentImportFormChange: (patch: Partial<AssignmentImportForm>) => void;
    onAssignmentCreate: (event: FormEvent<HTMLFormElement>) => void;
    onAssignmentImport: (event: FormEvent<HTMLFormElement>) => void;
    onAssignmentEdit: (assignment: DeliveryExamAssignment) => void;
    onAssignmentDeactivate: (assignment: DeliveryExamAssignment) => Promise<void>;
    onNewAssignment: () => void;
    onStationAssignmentFormChange: (patch: Partial<StationAssignmentForm>) => void;
    onStationAssignmentCreate: (event: FormEvent<HTMLFormElement>) => void;
    onStationAssignmentAutoAssign: () => Promise<void>;
    onStationAssignmentEdit: (assignment: DeliveryStationAssignment) => void;
    onStationAssignmentDeactivate: (assignment: DeliveryStationAssignment) => Promise<void>;
    onNewStationAssignment: () => void;
    onSittingRuntimePrepare: () => Promise<void>;
    onSittingStatusChange: (status: string) => Promise<void>;
    onRefreshSittingReadiness: () => Promise<void>;
  }
) {
  switch (key) {
    case 'overview':
      return <OverviewPanel snapshot={snapshot} onSelect={handlers.onSelect} />;
    case 'blueprint':
    case 'exam-version':
    case 'delivery-type':
    case 'paper':
    case 'questions':
    case 'response-profile':
    case 'grading-profile':
    case 'expected-answer':
    case 'version-readiness':
      return (
        <ExamVersionPanel
          mode={key}
          exams={snapshot.exams}
          classSections={snapshot.classSections}
          assessmentTypes={snapshot.assessmentTypes}
          versions={snapshot.examVersions}
          selectedExamId={handlers.selectedExamId}
          selectedExamVersionId={handlers.selectedExamVersionId}
          examForm={handlers.examForm}
          examSubmitting={handlers.examSubmitting}
          examMessage={handlers.examMessage}
          examError={handlers.examError}
          versionForm={handlers.versionForm}
          submitting={handlers.versionSubmitting}
          submitMessage={handlers.versionMessage}
          submitError={handlers.versionError}
          versionPublishing={handlers.versionPublishing}
          versionPublishMessage={handlers.versionPublishMessage}
          versionPublishError={handlers.versionPublishError}
          versionPublishBlockers={handlers.versionPublishBlockers}
          examActivationLoading={handlers.examActivationLoading}
          onPublishVersion={handlers.onPublishVersion}
          onActivateExamBlueprint={handlers.onActivateExamBlueprint}
          onSelect={handlers.onSelect}
          paperAssets={handlers.paperAssets}
          paperAssetsLoading={handlers.paperAssetsLoading}
          paperSubmitting={handlers.paperSubmitting}
          paperMessage={handlers.paperMessage}
          paperError={handlers.paperError}
          deliveryProfile={handlers.deliveryProfile}
          deliveryContentType={handlers.deliveryContentType}
          gradingProfiles={handlers.gradingProfiles}
          profileLoading={handlers.profileLoading}
          profileSubmitting={handlers.profileSubmitting}
          profileMessage={handlers.profileMessage}
          profileError={handlers.profileError}
          versionQuestions={handlers.versionQuestions}
          questionReadiness={handlers.questionReadiness}
          questionForm={handlers.questionForm}
          questionSubmitting={handlers.questionSubmitting}
          questionMessage={handlers.questionMessage}
          questionError={handlers.questionError}
          onSelectExam={handlers.onSelectExam}
          onSelectExamVersion={handlers.onSelectExamVersion}
          onExamFormChange={handlers.onExamFormChange}
          onExamSubmit={handlers.onExamSubmit}
          onFormChange={handlers.onVersionFormChange}
          onSubmit={handlers.onVersionSubmit}
          onUploadPaperAsset={handlers.onUploadPaperAsset}
          onRetirePaperAsset={handlers.onRetirePaperAsset}
          onDeliveryContentTypeChange={handlers.onDeliveryContentTypeChange}
          onSaveDeliveryContentType={handlers.onSaveDeliveryContentType}
          onConfigureFileUploadManualGrading={handlers.onConfigureFileUploadManualGrading}
          onApplyFileUploadPreset={handlers.onApplyFileUploadPreset}
          onCreatePlaceholderQuestion={handlers.onCreatePlaceholderQuestion}
          onRetireGradingProfile={handlers.onRetireGradingProfile}
          onQuestionFormChange={handlers.onQuestionFormChange}
          onQuestionTypeChange={handlers.onQuestionTypeChange}
          onQuestionSubmit={handlers.onQuestionSubmit}
          onQuestionSaveDraft={handlers.onQuestionSaveDraft}
          onQuestionEdit={handlers.onQuestionEdit}
        />
      );
    case 'sittings':
      return (
        <SittingsPanelMvp
          versions={snapshot.examVersions}
          sittings={handlers.sittings}
          selectedSittingId={handlers.selectedSittingId}
          sittingForm={handlers.sittingForm}
          sittingSubmitting={handlers.sittingSubmitting}
          sittingMessage={handlers.sittingMessage}
          sittingError={handlers.sittingError}
          onFormChange={handlers.onSittingFormChange}
          onSubmit={handlers.onSittingSubmit}
          onSelectSitting={handlers.onSittingSelect}
          onNewSitting={handlers.onNewSitting}
        />
      );
    case 'sitting-version':
      return (
        <SittingVersionPanel
          versions={snapshot.examVersions}
          selectedSitting={handlers.selectedSitting}
          appliedExamVersionId={handlers.appliedExamVersionId}
          appliedVersion={handlers.appliedVersion}
          submitting={handlers.sittingSubmitting}
          message={handlers.sittingMessage}
          error={handlers.sittingError}
          onAssign={handlers.onAssignSittingExamVersion}
        />
      );
    case 'rooms':
      return (
        <RoomsPanel
          rooms={snapshot.rooms}
          sittings={handlers.sittings}
          selectedSittingId={handlers.selectedSittingId}
          sittingRooms={handlers.sittingRooms}
          roomForm={handlers.sittingRoomForm}
          editingRoomId={handlers.editingSittingRoomId}
          submitting={handlers.roomSubmitting}
          message={handlers.roomMessage}
          error={handlers.roomError}
          onFormChange={handlers.onSittingRoomFormChange}
          onCreate={handlers.onSittingRoomCreate}
          onEdit={handlers.onSittingRoomEdit}
          onCancel={handlers.onSittingRoomCancel}
          onNew={handlers.onNewSittingRoom}
        />
      );
    case 'sitting-class-sections':
      return (
        <SittingClassSectionsPanel
          allClassSections={snapshot.classSections}
          sittingClassSections={handlers.sittingClassSections}
          classSectionDraft={handlers.classSectionDraft}
          selectedSittingId={handlers.selectedSittingId}
          selectedSitting={handlers.selectedSitting}
          loading={handlers.classSectionLoading}
          submitting={handlers.classSectionSubmitting}
          message={handlers.classSectionMessage}
          error={handlers.classSectionError}
          onToggle={handlers.onClassSectionToggle}
          onSave={handlers.onClassSectionSave}
          importing={handlers.classSectionImporting}
          onImportStudents={handlers.onClassSectionImport}
        />
      );
    case 'assignments':
      return (
        <AssignmentsPanel
          students={snapshot.students}
          assignments={handlers.assignments}
          selectedSittingId={handlers.selectedSittingId}
          selectedSitting={handlers.selectedSitting}
          form={handlers.assignmentForm}
          importForm={handlers.assignmentImportForm}
          editingAssignmentId={handlers.editingAssignmentId}
          submitting={handlers.assignmentSubmitting}
          message={handlers.assignmentMessage}
          error={handlers.assignmentError}
          onFormChange={handlers.onAssignmentFormChange}
          onImportFormChange={handlers.onAssignmentImportFormChange}
          onCreate={handlers.onAssignmentCreate}
          onImport={handlers.onAssignmentImport}
          onEdit={handlers.onAssignmentEdit}
          onDeactivate={handlers.onAssignmentDeactivate}
          onNew={handlers.onNewAssignment}
        />
      );
    case 'seating':
      return (
        <SeatingPanel
          stations={handlers.selectedRoomStations}
          sittingRooms={handlers.sittingRooms}
          assignments={handlers.assignments}
          seating={handlers.seatingPlan}
          stationLoading={handlers.selectedRoomStationsLoading}
          selectedSittingId={handlers.selectedSittingId}
          form={handlers.stationAssignmentForm}
          editingStationAssignmentId={handlers.editingStationAssignmentId}
          submitting={handlers.seatingSubmitting}
          message={handlers.seatingMessage}
          error={handlers.seatingError}
          onFormChange={handlers.onStationAssignmentFormChange}
          onCreate={handlers.onStationAssignmentCreate}
          onAutoAssign={handlers.onStationAssignmentAutoAssign}
          onEdit={handlers.onStationAssignmentEdit}
          onDeactivate={handlers.onStationAssignmentDeactivate}
          onNew={handlers.onNewStationAssignment}
        />
      );
    case 'proctors':
      return (
        <ProctorsPanel
          instructors={snapshot.instructors}
          sittingRooms={handlers.sittingRooms}
          proctors={handlers.proctors}
          selectedSittingId={handlers.selectedSittingId}
          form={handlers.proctorForm}
          editingProctorId={handlers.editingProctorId}
          submitting={handlers.proctorSubmitting}
          message={handlers.proctorMessage}
          error={handlers.proctorError}
          onFormChange={handlers.onProctorFormChange}
          onCreate={handlers.onProctorCreate}
          onEdit={handlers.onProctorEdit}
          onCancel={handlers.onProctorCancel}
          onNew={handlers.onNewProctor}
        />
      );
    case 'publish':
      return (
        <PublishPanel
          sittings={handlers.sittings}
          selectedSittingId={handlers.selectedSittingId}
          selectedSitting={handlers.selectedSitting}
          sittingReadiness={handlers.sittingReadiness}
          sittingReadinessLoading={handlers.sittingReadinessLoading}
          sittingReadinessError={handlers.sittingReadinessError}
          sittingReadinessStale={handlers.sittingReadinessStale}
          submitting={handlers.publishSubmitting}
          message={handlers.publishMessage}
          error={handlers.publishError}
          onSelect={handlers.onSelect}
          onSelectSitting={handlers.onSittingSelect}
          onPrepare={handlers.onSittingRuntimePrepare}
          onChangeStatus={handlers.onSittingStatusChange}
          onRefreshReadiness={handlers.onRefreshSittingReadiness}
        />
      );
    case 'readiness':
      return (
        <SittingReadinessPanel
          selectedSitting={handlers.selectedSitting}
          sittingReadiness={handlers.sittingReadiness}
          sittingReadinessLoading={handlers.sittingReadinessLoading}
          sittingReadinessError={handlers.sittingReadinessError}
          sittingReadinessStale={handlers.sittingReadinessStale}
          onSelect={handlers.onSelect}
          onRefresh={handlers.onRefreshSittingReadiness}
        />
      );
    default:
      return null;
  }
}

type ExamSetupPageProps = {
  allowedSectionKeys?: SetupSectionKey[];
  initialSectionKey?: SetupSectionKey;
  surfaceEyebrow?: string;
  surfaceTitle?: string;
  surfaceDescription?: string;
  testId?: string;
};

export function ExamSetupPage({
  allowedSectionKeys,
  initialSectionKey = 'overview',
  surfaceEyebrow = 'Exam setup',
  surfaceTitle = 'Thiết lập trước khi thi',
  surfaceDescription =
    'Giao diện chuẩn bị đề, ca thi, phòng, sinh viên, chỗ ngồi và giám thị. Những API đã có được nối dữ liệu thật; phần còn thiếu được giữ dạng khung để triển khai backend sau.',
  testId = 'exam-setup-page',
}: ExamSetupPageProps = {}) {
  const visibleSections = useMemo(() => {
    if (!allowedSectionKeys || allowedSectionKeys.length === 0) {
      return setupSections;
    }
    const allowedSet = new Set(allowedSectionKeys);
    return setupSections.filter((section) => allowedSet.has(section.key));
  }, [allowedSectionKeys]);
  const [activeKey, setActiveKey] = useState<SetupSectionKey>(() => {
    const allowedSet = allowedSectionKeys ? new Set(allowedSectionKeys) : null;
    if (allowedSet?.has(initialSectionKey)) {
      return initialSectionKey;
    }
    return visibleSections[0]?.key ?? 'overview';
  });
  const [snapshot, setSnapshot] = useState<ApiSnapshot>(initialSnapshot);
  const [selectedExamId, setSelectedExamId] = useState('');
  const [examForm, setExamForm] = useState<ExamForm>(initialExamForm);
  const [examSubmitting, setExamSubmitting] = useState(false);
  const [examMessage, setExamMessage] = useState<string | null>(null);
  const [examError, setExamError] = useState<string | null>(null);
  const [versionForm, setVersionForm] = useState<VersionForm>(initialVersionForm);
  const [versionSubmitting, setVersionSubmitting] = useState(false);
  const [versionMessage, setVersionMessage] = useState<string | null>(null);
  const [versionError, setVersionError] = useState<string | null>(null);
  const [versionPublishing, setVersionPublishing] = useState(false);
  const [versionPublishMessage, setVersionPublishMessage] = useState<string | null>(null);
  const [versionPublishError, setVersionPublishError] = useState<string | null>(null);
  const [versionPublishBlockers, setVersionPublishBlockers] = useState<PublishValidationBlocker[]>([]);
  const [examActivationLoading, setExamActivationLoading] = useState(false);
  const [selectedExamVersionId, setSelectedExamVersionId] = useState('');
  const [paperAssets, setPaperAssets] = useState<ExamVersionPaperAsset[]>([]);
  const [paperAssetsLoading, setPaperAssetsLoading] = useState(false);
  const [paperSubmitting, setPaperSubmitting] = useState(false);
  const [paperMessage, setPaperMessage] = useState<string | null>(null);
  const [paperError, setPaperError] = useState<string | null>(null);
  const [deliveryProfile, setDeliveryProfile] = useState<ExamVersionDeliveryProfile | null>(null);
  const [deliveryContentType, setDeliveryContentType] = useState<DeliveryContentType | ''>('');
  const [gradingProfiles, setGradingProfiles] = useState<QuestionGradingProfileSummary[]>([]);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileSubmitting, setProfileSubmitting] = useState(false);
  const [profileMessage, setProfileMessage] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [versionQuestions, setVersionQuestions] = useState<ExamVersionQuestionAuthoringItem[]>([]);
  const [questionReadiness, setQuestionReadiness] = useState<{ ready: boolean; missing_items: Array<Record<string, unknown>> }>({
    ready: false,
    missing_items: [],
  });
  const [appliedVersionQuestions, setAppliedVersionQuestions] = useState<ExamVersionQuestionAuthoringItem[]>([]);
  const [appliedQuestionReadiness, setAppliedQuestionReadiness] = useState<{
    ready: boolean;
    missing_items: Array<Record<string, unknown>>;
  }>({ ready: false, missing_items: [] });
  const [questionForm, setQuestionForm] = useState<VersionQuestionForm>(initialVersionQuestionForm);
  const [questionSubmitting, setQuestionSubmitting] = useState(false);
  const [questionMessage, setQuestionMessage] = useState<string | null>(null);
  const [questionError, setQuestionError] = useState<string | null>(null);
  const [sittings, setSittings] = useState<SetupSitting[]>([]);
  const [selectedSittingId, setSelectedSittingId] = useState('');
  const [sittingRooms, setSittingRooms] = useState<DeliverySittingRoom[]>([]);
  const [proctors, setProctors] = useState<DeliveryProctorAssignment[]>([]);
  const [assignments, setAssignments] = useState<DeliveryExamAssignment[]>([]);
  const [seatingPlan, setSeatingPlan] = useState<DeliveryStationAssignment[]>([]);
  const [selectedRoomStations, setSelectedRoomStations] = useState<ExamSetupRow[]>([]);
  const [selectedRoomStationsLoading, setSelectedRoomStationsLoading] = useState(false);
  const [sittingForm, setSittingForm] = useState<SittingForm>(initialSittingForm);
  const [sittingRoomForm, setSittingRoomForm] = useState<SittingRoomForm>(initialSittingRoomForm);
  const [proctorForm, setProctorForm] = useState<ProctorForm>(initialProctorForm);
  const [assignmentForm, setAssignmentForm] = useState<AssignmentForm>(initialAssignmentForm);
  const [assignmentImportForm, setAssignmentImportForm] = useState<AssignmentImportForm>(initialAssignmentImportForm);
  const [stationAssignmentForm, setStationAssignmentForm] = useState<StationAssignmentForm>(initialStationAssignmentForm);
  const [editingSittingRoomId, setEditingSittingRoomId] = useState('');
  const [editingProctorId, setEditingProctorId] = useState('');
  const [editingAssignmentId, setEditingAssignmentId] = useState('');
  const [editingStationAssignmentId, setEditingStationAssignmentId] = useState('');
  const [sittingSubmitting, setSittingSubmitting] = useState(false);
  const [sittingMessage, setSittingMessage] = useState<string | null>(null);
  const [sittingError, setSittingError] = useState<string | null>(null);
  const [roomSubmitting, setRoomSubmitting] = useState(false);
  const [roomMessage, setRoomMessage] = useState<string | null>(null);
  const [roomError, setRoomError] = useState<string | null>(null);
  const [proctorSubmitting, setProctorSubmitting] = useState(false);
  const [proctorMessage, setProctorMessage] = useState<string | null>(null);
  const [proctorError, setProctorError] = useState<string | null>(null);
  const [assignmentSubmitting, setAssignmentSubmitting] = useState(false);
  const [assignmentMessage, setAssignmentMessage] = useState<string | null>(null);
  const [assignmentError, setAssignmentError] = useState<string | null>(null);
  const [seatingSubmitting, setSeatingSubmitting] = useState(false);
  const [seatingMessage, setSeatingMessage] = useState<string | null>(null);
  const [seatingError, setSeatingError] = useState<string | null>(null);
  const [sittingReadiness, setSittingReadiness] = useState<SittingReadiness | null>(null);
  const [sittingReadinessLoading, setSittingReadinessLoading] = useState(false);
  const [sittingReadinessError, setSittingReadinessError] = useState<string | null>(null);
  const [sittingReadinessStale, setSittingReadinessStale] = useState(false);
  const [publishSubmitting, setPublishSubmitting] = useState(false);
  const [publishMessage, setPublishMessage] = useState<string | null>(null);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [sittingClassSections, setSittingClassSections] = useState<SittingClassSection[]>([]);
  const [classSectionDraft, setClassSectionDraft] = useState<Set<number>>(new Set());
  const [classSectionLoading, setClassSectionLoading] = useState(false);
  const [classSectionSubmitting, setClassSectionSubmitting] = useState(false);
  const [classSectionMessage, setClassSectionMessage] = useState<string | null>(null);
  const [classSectionError, setClassSectionError] = useState<string | null>(null);
  const [classSectionImporting, setClassSectionImporting] = useState(false);
  const activeSection = visibleSections.find((section) => section.key === activeKey) ?? visibleSections[0] ?? setupSections[0];
  const showApiDiagnostics = isUiApiDiagnosticsEnabled();
  const selectedSitting = useMemo(
    () => sittings.find((item) => String(item.exam_sitting_id) === selectedSittingId),
    [sittings, selectedSittingId]
  );
  const appliedExamVersionId = selectedSitting?.exam_version_id ? String(selectedSitting.exam_version_id) : '';
  const appliedVersion = snapshot.examVersions.find((version) => getId(version, 'exam_version_id') === appliedExamVersionId);

  const visibleSectionGroups = useMemo(
    () =>
      sectionGroups
        .map((group) => ({
          ...group,
          sections: visibleSections.filter((section) => group.keys.includes(section.key)),
        }))
        .filter((group) => group.sections.length > 0),
    [visibleSections]
  );
  const hasAuthoringSurface = useMemo(
    () => visibleSections.some((section) => section.key === 'overview' || authoringSectionKeys.includes(section.key)),
    [visibleSections]
  );
  const hasDeliverySurface = useMemo(
    () => visibleSections.some((section) => deliverySectionKeys.includes(section.key)),
    [visibleSections]
  );
  const selectedExamStatus = asString(
    snapshot.exams.find((exam) => getId(exam, 'exam_id') === selectedExamId)?.exam_status,
    examForm.exam_status || '-'
  );

  useEffect(() => {
    if (visibleSections.length === 0) {
      return;
    }
    const activeStillVisible = visibleSections.some((section) => section.key === activeKey);
    if (!activeStillVisible) {
      setActiveKey(visibleSections[0].key);
    }
  }, [activeKey, visibleSections]);

  async function loadBaseData() {
    setSnapshot((current) => ({ ...current, loading: true, error: null }));
    try {
      const [authoringData, deliveryData] = await Promise.all([
        hasAuthoringSurface ? loadExamAuthoringBaseData() : Promise.resolve(emptyExamSetupBaseData),
        hasDeliverySurface ? loadDeliverySetupBaseData() : Promise.resolve(emptyExamSetupBaseData),
      ]);
      const exams = authoringData.exams.length > 0 ? authoringData.exams : deliveryData.exams;
      const classSections = authoringData.classSections;
      const assessmentTypes = authoringData.assessmentTypes;
      const rooms = deliveryData.rooms;
      const stations = deliveryData.stations;
      const students = deliveryData.students;
      const instructors = deliveryData.instructors;
      const modules = deliveryData.modules;

      setSnapshot((current) => ({
        ...current,
        exams,
        classSections,
        assessmentTypes,
        rooms,
        stations,
        students,
        instructors,
        modules,
        loading: false,
        error: null,
      }));

      if (!selectedExamId && exams.length > 0) {
        setSelectedExamId(getId(exams[0], 'exam_id'));
      }
      setExamForm((current) => ({
        ...current,
        assessment_type_id:
          current.assessment_type_id || (assessmentTypes.length > 0 ? getId(assessmentTypes[0], 'assessment_type_id') : ''),
      }));
      return {
        exams,
        classSections,
        assessmentTypes,
        rooms,
        stations,
        students,
        instructors,
        modules,
      };
    } catch (error) {
      setSnapshot((current) => ({
        ...current,
        loading: false,
        error: error instanceof Error ? error.message : 'Không tải được dữ liệu API.',
      }));
      return null;
    }
  }

  async function loadExamVersions(examId: string, preferredVersionId = selectedExamVersionId) {
    if (!examId) {
      setSnapshot((current) => ({ ...current, examVersions: [] }));
      setSelectedExamVersionId('');
      setPaperAssets([]);
      return;
    }
    const versions = await fetchExamVersions(examId);
    setSnapshot((current) => ({ ...current, examVersions: versions }));
    const nextDefaultVersionId = versions.length > 0 ? getId(versions[0], 'exam_version_id') : '';
    const hasPreferredVersion = versions.some((version) => getId(version, 'exam_version_id') === preferredVersionId);
    if (!hasPreferredVersion) {
      if (preferredVersionId) {
        setQuestionError(questionVersionStaleMessage);
      }
      setSelectedExamVersionId(nextDefaultVersionId);
    } else {
      setSelectedExamVersionId(preferredVersionId);
      setQuestionError((current) => (current === questionVersionStaleMessage ? null : current));
    }
    const hasCurrentVersion = versions.some((version) => getId(version, 'exam_version_id') === sittingForm.exam_version_id);
    if (!hasCurrentVersion) {
      setSittingForm((current) => ({ ...current, exam_version_id: nextDefaultVersionId }));
    }
  }

  async function loadPaperAssets(examId: string, examVersionId: string) {
    if (!examId || !examVersionId) {
      setPaperAssets([]);
      return;
    }
    setPaperAssetsLoading(true);
    try {
      const items = await loadExamVersionPaperAssets(examId, examVersionId);
      setPaperAssets(items);
      setPaperError(null);
    } catch (error) {
      setPaperAssets([]);
      setPaperError(error instanceof Error ? error.message : 'Không tải được paper asset.');
    } finally {
      setPaperAssetsLoading(false);
    }
  }

  async function loadVersionProfiles(examVersionId: string) {
    if (!examVersionId) {
      setDeliveryProfile(null);
      setGradingProfiles([]);
      return;
    }
    setProfileLoading(true);
    try {
      const [profile, questionProfiles] = await Promise.all([
        loadExamVersionDeliveryProfile(examVersionId),
        loadExamVersionQuestionGradingProfiles(examVersionId),
      ]);
      setDeliveryProfile(profile);
      setGradingProfiles(questionProfiles);
      setProfileError(null);
    } catch (error) {
      setDeliveryProfile(null);
      setGradingProfiles([]);
      setProfileError(error instanceof Error ? error.message : 'Không tải được cấu hình profile.');
    } finally {
      setProfileLoading(false);
    }
  }

  async function loadVersionQuestions(examVersionId: string) {
    if (!examVersionId) {
      setVersionQuestions([]);
      setQuestionReadiness({ ready: false, missing_items: [] });
      setQuestionForm(initialVersionQuestionForm);
      setQuestionError((current) => (current === questionVersionStaleMessage ? current : questionVersionMissingMessage));
      return;
    }
    try {
      const result = await loadExamVersionQuestions(examVersionId);
      setVersionQuestions(result.items);
      setQuestionReadiness(result.readiness_summary);
      setQuestionError(null);
    } catch (error) {
      setVersionQuestions([]);
      setQuestionReadiness({ ready: false, missing_items: [] });
      setQuestionError(normalizeQuestionErrorMessage(error));
    }
  }

  async function loadAppliedVersionReadiness(examVersionId: string) {
    if (!examVersionId) {
      setAppliedVersionQuestions([]);
      setAppliedQuestionReadiness({ ready: false, missing_items: [] });
      return;
    }
    try {
      const result = await loadExamVersionQuestions(examVersionId);
      setAppliedVersionQuestions(result.items);
      setAppliedQuestionReadiness(result.readiness_summary);
    } catch {
      setAppliedVersionQuestions([]);
      setAppliedQuestionReadiness({
        ready: false,
        missing_items: [{ code: 'applied_version_readiness_unavailable' }],
      });
    }
  }

  async function loadSittings() {
    let items: SetupSitting[] = [];
    try {
      items = await listDeliverySittings();
    } catch {
      items = await listSetupSittings();
    }
    setSittings(items);
    if (items.length > 0 && !selectedSittingId) {
      setSelectedSittingId(String(items[0].exam_sitting_id));
    }
  }

  async function loadSittingData(examSittingId: number) {
    const [rooms, assignmentRows, seatingRows, readiness] = await Promise.all([
      listSittingRooms(examSittingId),
      listExamAssignments(examSittingId),
      listSeatingPlan(examSittingId),
      getExamSittingReadiness(examSittingId),
    ]);
    const activeAssignments = assignmentRows.filter(assignmentIsActive);
    const activeAssignmentIds = new Set(activeAssignments.map((assignment) => String(assignment.exam_assignment_id)));
    const activeSeatingRows = seatingRows
      .filter(stationAssignmentIsActive)
      .filter((assignment) => activeAssignmentIds.has(String(assignment.exam_assignment_id)));
    setSittingRooms(rooms);
    setAssignments(activeAssignments);
    setSeatingPlan(activeSeatingRows);
    setSittingReadiness(readiness);
    setSittingReadinessError(null);
    setSittingReadinessStale(false);
    if (rooms.length > 0) {
      setProctorForm((current) =>
        current.exam_sitting_room_id ? current : { ...current, exam_sitting_room_id: String(rooms[0].exam_sitting_room_id) }
      );
    }
    if (rooms.length > 0) {
      setStationAssignmentForm((current) =>
        current.exam_sitting_room_id ? current : { ...current, exam_sitting_room_id: String(rooms[0].exam_sitting_room_id) }
      );
    }
    if (activeAssignments.length > 0) {
      setStationAssignmentForm((current) =>
        current.exam_assignment_id && activeAssignmentIds.has(current.exam_assignment_id)
          ? current
          : { ...current, exam_assignment_id: String(activeAssignments[0].exam_assignment_id) }
      );
    } else {
      setStationAssignmentForm((current) => ({ ...current, exam_assignment_id: '' }));
    }
  }

  async function loadRoomProctors(examSittingRoomId: number) {
    const items = await listRoomProctors(examSittingRoomId);
    setProctors(items);
  }

  async function refreshSittingReadiness() {
    if (!selectedSittingId) {
      setSittingReadiness(null);
      setSittingReadinessError(null);
      setSittingReadinessStale(false);
      return;
    }
    setSittingReadinessLoading(true);
    try {
      await loadSittingData(Number(selectedSittingId));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Không tải được readiness của ca thi.';
      setSittingReadinessError(message);
      setSittingReadinessStale(true);
    } finally {
      setSittingReadinessLoading(false);
    }
  }

  function toIsoDateTime(value: string): string {
    if (!value) {
      return value;
    }
    return new Date(value).toISOString();
  }

  function toDateTimeLocal(value: string): string {
    if (!value) {
      return '';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return '';
    }
    const offsetDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return offsetDate.toISOString().slice(0, 16);
  }

  useEffect(() => {
    void loadBaseData();
    loadSittings().catch((error) => {
      setSittingError(error instanceof Error ? error.message : 'Không tải được danh sách ca thi.');
    });
  }, [hasAuthoringSurface, hasDeliverySurface]);

  useEffect(() => {
    const selectedRoom = sittingRooms.find(
      (room) => String(room.exam_sitting_room_id) === String(stationAssignmentForm.exam_sitting_room_id)
    );
    if (!selectedRoom?.room_id) {
      setSelectedRoomStations([]);
      setSelectedRoomStationsLoading(false);
      return;
    }

    let cancelled = false;
    setSelectedRoomStationsLoading(true);
    loadRoomStations(Number(selectedRoom.room_id))
      .then((items) => {
        if (!cancelled) {
          setSelectedRoomStations(items);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSelectedRoomStations([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setSelectedRoomStationsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [sittingRooms, stationAssignmentForm.exam_sitting_room_id]);

  useEffect(() => {
    if (!selectedExamId) {
      return;
    }
    const selectedExam = snapshot.exams.find((exam) => getId(exam, 'exam_id') === selectedExamId);
    if (selectedExam) {
      setExamForm((current) => ({
        ...current,
        exam_code: asString(selectedExam.exam_code, ''),
        exam_name: asString(selectedExam.exam_name, ''),
        class_section_id: selectedExam.class_section_id == null ? '' : asString(selectedExam.class_section_id, ''),
        assessment_type_id: asString(selectedExam.assessment_type_id, current.assessment_type_id),
        description: asString(selectedExam.description, ''),
        exam_status: asString(selectedExam.exam_status ?? selectedExam.status, current.exam_status),
      }));
    }
    loadExamVersions(selectedExamId).catch((error) => {
      setSnapshot((current) => ({
        ...current,
        examVersions: [],
        error: error instanceof Error ? error.message : 'Không tải được exam versions.',
      }));
    });
  }, [selectedExamId]);

  useEffect(() => {
    const selectedVersion = snapshot.examVersions.find((version) => getId(version, 'exam_version_id') === selectedExamVersionId);
    if (!selectedVersion) {
      return;
    }
    setVersionForm({
      version_label: asString(selectedVersion.version_label, ''),
      duration_minutes: String(Math.max(1, Math.round(asNumber(selectedVersion.duration_seconds, 5400) / 60))),
      total_score: asString(selectedVersion.total_score, '10'),
      randomization_mode: asString(selectedVersion.randomization_mode, 'FIXED'),
      status: asString(selectedVersion.status, 'DRAFT'),
    });
  }, [selectedExamVersionId, snapshot.examVersions]);

  useEffect(() => {
    setVersionPublishMessage(null);
    setVersionPublishError(null);
    setVersionPublishBlockers([]);
  }, [selectedExamVersionId]);

  useEffect(() => {
    if (!selectedSitting) {
      return;
    }
    setSittingForm({
      sitting_code: selectedSitting.sitting_code || '',
      sitting_name: selectedSitting.sitting_name || '',
      exam_version_id: selectedSitting.exam_version_id ? String(selectedSitting.exam_version_id) : '',
      scheduled_start_at: toDateTimeLocal(selectedSitting.scheduled_start_at),
      scheduled_end_at: toDateTimeLocal(selectedSitting.scheduled_end_at),
      status: selectedSitting.sitting_status || 'DRAFT',
    });
  }, [selectedSitting]);

  useEffect(() => {
    void loadPaperAssets(selectedExamId, selectedExamVersionId);
  }, [selectedExamId, selectedExamVersionId]);

  useEffect(() => {
    void loadVersionProfiles(selectedExamVersionId);
  }, [selectedExamVersionId]);

  useEffect(() => {
    setDeliveryContentType(getDeliveryContentType(deliveryProfile));
  }, [deliveryProfile]);

  useEffect(() => {
    void loadVersionQuestions(selectedExamVersionId);
  }, [selectedExamVersionId]);

  useEffect(() => {
    void loadAppliedVersionReadiness(appliedExamVersionId);
  }, [appliedExamVersionId]);

  useEffect(() => {
    resetSittingRoomForm();
    resetProctorForm();
    resetAssignmentForm();
    setAssignmentImportForm(initialAssignmentImportForm);
    resetStationAssignmentForm();
    if (!selectedSittingId) {
      setSittingRooms([]);
      setAssignments([]);
      setSeatingPlan([]);
      setSittingReadiness(null);
      setSittingReadinessError(null);
      setSittingReadinessStale(false);
      setSittingClassSections([]);
      setClassSectionDraft(new Set());
      return;
    }
    setSittingReadinessLoading(true);
    setClassSectionLoading(true);
    loadSittingData(Number(selectedSittingId)).catch((error) => {
      const message = error instanceof Error ? error.message : 'Không tải được dữ liệu ca thi.';
      setRoomError(message);
      setAssignmentError(message);
      setSeatingError(message);
      setSittingReadinessError(message);
      setSittingReadiness(null);
    }).finally(() => {
      setSittingReadinessLoading(false);
    });
    listSittingClassSections(Number(selectedSittingId)).then((items) => {
      setSittingClassSections(items);
      setClassSectionDraft(new Set(items.map((r) => r.class_section_id)));
    }).catch(() => {
      // Non-fatal — class sections may not exist yet
      setSittingClassSections([]);
      setClassSectionDraft(new Set());
    }).finally(() => {
      setClassSectionLoading(false);
    });
  }, [selectedSittingId]);

  useEffect(() => {
    if (!proctorForm.exam_sitting_room_id) {
      setProctors([]);
      return;
    }
    loadRoomProctors(Number(proctorForm.exam_sitting_room_id)).catch((error) => {
      setProctorError(error instanceof Error ? error.message : 'Không tải được danh sách giám thị.');
    });
  }, [proctorForm.exam_sitting_room_id]);

  async function handleCreateExam(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!examForm.assessment_type_id) {
      setExamError('Cần chọn hình thức đánh giá.');
      return;
    }

    setExamSubmitting(true);
    setExamError(null);
    setExamMessage(null);

    const payload = {
      exam_code: examForm.exam_code.trim(),
      exam_name: examForm.exam_name.trim(),
      class_section_id: examForm.class_section_id ? Number(examForm.class_section_id) : null,
      assessment_type_id: Number(examForm.assessment_type_id),
      description: examForm.description.trim() || null,
      exam_status: examForm.exam_status,
    };
    const response = selectedExamId ? await updateExam(selectedExamId, payload) : await createExam(payload);

    setExamSubmitting(false);
    if (!response.ok) {
      setExamError(response.error.message);
      return;
    }

    const savedExamId = response.data?.exam_id ? String(response.data.exam_id) : selectedExamId;
    setExamForm((current) => ({
      ...initialExamForm,
      assessment_type_id: current.assessment_type_id,
    }));
    setExamMessage(selectedExamId ? 'Đã cập nhật đề gốc.' : 'Đã tạo đề gốc.');
    await loadBaseData();
    if (savedExamId) {
      setSelectedExamId(savedExamId);
    }
  }

  async function handleCreateVersion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedExamId) {
      setVersionError('Cần chọn đề thi trước khi tạo version.');
      return;
    }

    setVersionSubmitting(true);
    setVersionError(null);
    setVersionMessage(null);

    const payload = {
      version_label: versionForm.version_label.trim() || null,
      duration_seconds: Math.max(1, Number(versionForm.duration_minutes)) * 60,
      total_score: Number(versionForm.total_score),
      shuffle_questions: versionForm.randomization_mode !== 'FIXED',
      shuffle_options: versionForm.randomization_mode !== 'FIXED',
      randomization_mode: versionForm.randomization_mode,
      status: versionForm.status,
    };
    const response = selectedExamVersionId
      ? await updateExamVersion(selectedExamVersionId, payload)
      : await createExamVersion(selectedExamId, payload);

    setVersionSubmitting(false);
    if (!response.ok) {
      setVersionError(response.error.message);
      return;
    }

    const savedVersionId = response.data?.exam_version_id ? String(response.data.exam_version_id) : selectedExamVersionId;
    setVersionForm(initialVersionForm);
    setVersionMessage(selectedExamVersionId ? 'Đã cập nhật phiên bản đề.' : 'Đã tạo phiên bản đề.');
    if (savedVersionId) {
      await loadExamVersions(selectedExamId, savedVersionId);
    } else {
      await loadExamVersions(selectedExamId);
    }
  }

  async function refreshSelectedVersionPublishReadiness() {
    if (!selectedExamVersionId) {
      return false;
    }

    const validationResponse = await validateExamVersion(selectedExamVersionId);
    if (!validationResponse.ok) {
      const blockers = publishBlockersFromDetails(validationResponse.error.details);
      setVersionPublishBlockers(blockers);
      setVersionPublishError(
        blockers.length > 0
          ? 'Phiên bản chưa sẵn sàng để publish. Hãy sửa các blocker bên dưới.'
          : validationResponse.error.message
      );
      return false;
    }

    const blockers = normalizePublishBlockers(validationResponse.data.missing_items);
    setVersionPublishBlockers(blockers);
    if (!validationResponse.data.is_valid || blockers.length > 0) {
      setVersionPublishError('Phiên bản chưa sẵn sàng để publish. Hãy sửa các blocker bên dưới.');
      return false;
    }

    setVersionPublishError(null);
    return true;
  }

  async function handleActivateExamBlueprint() {
    if (!selectedExamId) {
      setVersionPublishError('Cần chọn đề gốc trước khi kích hoạt.');
      return;
    }

    setExamActivationLoading(true);
    setVersionPublishMessage(null);
    setVersionPublishError(null);

    try {
      const latestBaseData = await loadBaseData();
      let latestExam =
        latestBaseData?.exams.find((exam) => getId(exam, 'exam_id') === selectedExamId) ??
        snapshot.exams.find((exam) => getId(exam, 'exam_id') === selectedExamId);
      const currentStatus = getExamStatus(latestExam, examForm.exam_status || 'DRAFT');

      if (examActivationBlockedStatuses.has(currentStatus)) {
        setVersionPublishError(`Không thể tự động kích hoạt đề gốc ở trạng thái ${currentStatus}. Hãy tạo đề gốc mới hoặc xử lý theo quy trình quản trị.`);
        return;
      }

      if (!['DRAFT', 'READY', 'ACTIVE'].includes(currentStatus)) {
        setVersionPublishError(`Không hỗ trợ tự động kích hoạt đề gốc từ trạng thái ${currentStatus || 'không xác định'}.`);
        return;
      }

      const targetStatuses = currentStatus === 'DRAFT' ? ['READY', 'ACTIVE'] : currentStatus === 'READY' ? ['ACTIVE'] : [];
      for (const nextStatus of targetStatuses) {
        const response = await updateExam(selectedExamId, buildExamStatusUpdatePayload(latestExam, examForm, nextStatus));
        if (!response.ok) {
          setVersionPublishError(response.error.message);
          return;
        }
        latestExam = response.data ? ({ ...latestExam, ...response.data } as ExamSetupRow) : ({ ...latestExam, exam_status: nextStatus } as ExamSetupRow);
      }

      await loadBaseData();
      await loadExamVersions(selectedExamId, selectedExamVersionId);
      const ready = await refreshSelectedVersionPublishReadiness();
      setVersionPublishMessage(
        ready
          ? 'Đề gốc đã ACTIVE. Phiên bản đề đã sẵn sàng để publish.'
          : 'Đã kích hoạt đề gốc. ACTIVE thuộc đề gốc/blueprint; PUBLISHED thuộc phiên bản đề.'
      );
    } catch (error) {
      setVersionPublishError(error instanceof Error ? error.message : 'Không thể kích hoạt đề gốc.');
    } finally {
      setExamActivationLoading(false);
    }
  }

  async function handlePublishVersion() {
    if (!selectedExamVersionId) return;
    setVersionPublishing(true);
    setVersionPublishMessage(null);
    setVersionPublishError(null);
    setVersionPublishBlockers([]);

    const validationResponse = await validateExamVersion(selectedExamVersionId);
    if (!validationResponse.ok) {
      const blockers = publishBlockersFromDetails(validationResponse.error.details);
      setVersionPublishing(false);
      setVersionPublishBlockers(blockers);
      setVersionPublishError(
        blockers.length > 0
          ? 'Phiên bản chưa sẵn sàng để publish. Hãy sửa các blocker bên dưới.'
          : validationResponse.error.message
      );
      return;
    }

    const validationBlockers = normalizePublishBlockers(validationResponse.data.missing_items);
    if (!validationResponse.data.is_valid || validationBlockers.length > 0) {
      setVersionPublishing(false);
      setVersionPublishBlockers(validationBlockers);
      setVersionPublishError('Phiên bản chưa sẵn sàng để publish. Hãy sửa các blocker bên dưới.');
      return;
    }

    const response = await publishExamVersion(selectedExamVersionId);
    setVersionPublishing(false);
    if (!response.ok) {
      const publishBlockers = publishBlockersFromDetails(response.error.details);
      if (response.error.code === 'validation_error' || response.error.code === 'master_data_validation_error' || publishBlockers.length > 0) {
        setVersionPublishBlockers(
          publishBlockers.length > 0
            ? publishBlockers
            : [
                {
                  code: response.error.code,
                  message: response.error.message,
                  severity: null,
                  status: null,
                  sectionKey: null,
                  sectionTitle: null,
                },
              ]
        );
        setVersionPublishError('Không thể publish phiên bản đề. Hãy sửa các blocker bên dưới.');
        return;
      }
      setVersionPublishError(response.error.message);
      return;
    }
    setVersionPublishBlockers([]);
    setVersionPublishMessage('Đã publish phiên bản đề.');
    await loadExamVersions(selectedExamId, selectedExamVersionId);
  }

  async function handleUploadPaperAsset(file: File) {
    if (!selectedExamId || !selectedExamVersionId) {
      setPaperError('Cần chọn exam và version trước khi upload.');
      return;
    }

    setPaperSubmitting(true);
    setPaperError(null);
    setPaperMessage(null);
    const response = await uploadExamVersionPaperAsset(selectedExamId, selectedExamVersionId, file);
    setPaperSubmitting(false);
    if (!response.ok) {
      setPaperError(response.error.message);
      return;
    }

    setPaperMessage('Upload paper asset thành công.');
    await loadPaperAssets(selectedExamId, selectedExamVersionId);
  }

  async function handleRetirePaperAsset(paperAssetId: number) {
    if (!selectedExamId || !selectedExamVersionId) {
      setPaperError('Cần chọn exam và version trước khi retire.');
      return;
    }

    setPaperSubmitting(true);
    setPaperError(null);
    setPaperMessage(null);
    const response = await retireExamVersionPaperAsset(selectedExamId, selectedExamVersionId, paperAssetId);
    setPaperSubmitting(false);
    if (!response.ok) {
      setPaperError(response.error.message);
      return;
    }
    setPaperMessage('Đã retire paper asset.');
    await loadPaperAssets(selectedExamId, selectedExamVersionId);
  }

  async function handleSaveDeliveryContentType() {
    if (!selectedExamVersionId) {
      setProfileError('Cần chọn phiên bản đề trước khi lưu dạng đề.');
      return;
    }
    if (!deliveryContentType) {
      setProfileError('Cần chọn dạng đề.');
      return;
    }

    setProfileSubmitting(true);
    setProfileMessage(null);
    setProfileError(null);
    const response = await upsertExamVersionDeliveryProfile(
      selectedExamVersionId,
      buildDeliveryProfilePayload(deliveryContentType, deliveryProfile)
    );
    setProfileSubmitting(false);
    if (!response.ok) {
      setProfileError(response.error.message);
      return;
    }
    setDeliveryProfile(response.data);
    setProfileMessage(`Đã lưu dạng đề ${deliveryContentType}.`);
    await loadVersionProfiles(selectedExamVersionId);
  }

  async function handleApplyFileUploadPreset() {
    if (!selectedExamVersionId) {
      setProfileError('Cần chọn version đề thi trước khi áp dụng preset.');
      return;
    }
    setProfileSubmitting(true);
    setProfileMessage(null);
    setProfileError(null);

    const deliveryResponse = await upsertExamVersionDeliveryProfile(
      selectedExamVersionId,
      buildDeliveryProfilePayload('FILE_SUBMISSION_BASED', deliveryProfile)
    );
    if (!deliveryResponse.ok) {
      setProfileSubmitting(false);
      setProfileError(deliveryResponse.error.message);
      return;
    }

    const activeManual = gradingProfiles.find(
      (profile) =>
        String(profile.status).toUpperCase() === 'ACTIVE' &&
        String(profile.comparison_method).toUpperCase() === 'MANUAL_RUBRIC'
    );
    if (!activeManual && gradingProfiles.length === 0) {
      setProfileSubmitting(false);
      setProfileError('Chưa có câu hỏi để tạo question grading profile. Vui lòng tạo câu hỏi trước.');
      await loadVersionProfiles(selectedExamVersionId);
      return;
    }

    for (const profile of gradingProfiles) {
      const patchResponse = await patchQuestionGradingProfile(Number(profile.question_grading_profile_id), {
        input_source: 'SEALED_FILE_REF',
        answer_language: 'NONE',
        requires_capture: false,
        required_capture_type: null,
        capture_profile_id: null,
        grading_engine_code: 'MANUAL_RUBRIC',
        comparison_method: 'MANUAL_RUBRIC',
        metadata_json: {
          answer_format: 'FILE_REF',
          manual_review_policy: 'ALWAYS',
        },
      });
      if (!patchResponse.ok) {
        setProfileSubmitting(false);
        setProfileError(patchResponse.error.message);
        return;
      }
    }

    setProfileSubmitting(false);
    setProfileMessage('Đã áp dụng cấu hình nộp tệp + chấm thủ công.');
    await loadVersionProfiles(selectedExamVersionId);
    await loadVersionQuestions(selectedExamVersionId);
  }

  async function handleConfigureFileUploadManualGrading() {
    if (!selectedExamVersionId) {
      setProfileError('Cần chọn version đề thi trước khi cấu hình.');
      return;
    }
    setProfileSubmitting(true);
    setProfileMessage(null);
    setProfileError(null);

    const response = await configureFileUploadManualGrading(selectedExamVersionId, {
      question_label: 'Nộp tệp bài làm',
      question_text: 'Đính kèm bài làm theo yêu cầu trong đề thi.',
      max_score: 10,
      required: true,
      allowed_extensions: ['.zip', '.pdf', '.docx', '.xlsx', '.csv', '.sql', '.txt', '.json'],
      allowed_mime_types: [
        'application/zip',
        'application/x-zip-compressed',
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/csv',
        'application/csv',
        'text/plain',
        'application/sql',
        'application/json',
        'text/json',
      ],
      max_file_size_bytes: 26214400,
    });

    setProfileSubmitting(false);
    if (!response.ok) {
      setProfileError('Không thể cấu hình nộp tệp. Vui lòng thử lại.');
      return;
    }
    setProfileMessage('Đã cấu hình nộp tệp + chấm thủ công.');
    await loadVersionProfiles(selectedExamVersionId);
    await loadVersionQuestions(selectedExamVersionId);
  }

  async function handleCreatePlaceholderQuestion() {
    if (!selectedExamVersionId) {
      setProfileError('Cần chọn version đề thi trước khi tạo câu hỏi.');
      return;
    }
    setProfileSubmitting(true);
    setProfileMessage(null);
    setProfileError(null);
    const response = await createFileUploadPlaceholderQuestion(selectedExamVersionId, {
      question_label: 'Nộp tệp bài làm',
      question_text: 'Đính kèm bài làm theo yêu cầu trong đề thi.',
      max_score: 10,
      required: true,
      allowed_extensions: ['.zip', '.pdf', '.docx', '.xlsx', '.csv', '.sql', '.txt', '.json'],
      allowed_mime_types: [
        'application/zip',
        'application/x-zip-compressed',
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/csv',
        'application/csv',
        'application/sql',
        'text/plain',
        'application/json',
        'text/json',
      ],
      max_file_size_bytes: 26214400,
    });
    setProfileSubmitting(false);
    if (!response.ok) {
      setProfileError(response.error.message);
      return;
    }
    setProfileMessage('Đã tạo câu nộp tệp bài làm.');
    await loadVersionProfiles(selectedExamVersionId);
    await loadVersionQuestions(selectedExamVersionId);
  }

  async function handleRetireGradingProfile(questionGradingProfileId: number) {
    setProfileSubmitting(true);
    setProfileMessage(null);
    setProfileError(null);
    const response = await retireQuestionGradingProfile(
      questionGradingProfileId,
      'Retire từ màn hình cấu hình admin'
    );
    setProfileSubmitting(false);
    if (!response.ok) {
      setProfileError(response.error.message);
      return;
    }
    setProfileMessage('Đã retire question grading profile.');
    await loadVersionProfiles(selectedExamVersionId);
    await loadVersionQuestions(selectedExamVersionId);
  }

  function handleQuestionTypeChange(questionType: VersionQuestionForm['question_type']) {
    const defaults = questionTypeDefaults(questionType);
    setQuestionForm((current) => ({
      ...current,
      question_type: questionType,
      response_mode: defaults.response_mode,
      render_component: defaults.render_component,
      grading_engine_code: defaults.grading_engine_code,
      comparison_method: defaults.comparison_method,
    }));
  }

  function handleQuestionEdit(item: ExamVersionQuestionAuthoringItem) {
    setQuestionForm({
      question_template_id: String(item.question_template_id),
      question_no: String(item.question_no || 1),
      question_title: item.question_title || '',
      prompt_text: item.prompt_text || '',
      question_type: (['TEXTAREA', 'TEXTBOX_SQL', 'FILE_UPLOAD', 'MCQ_SINGLE'].includes(item.question_type)
        ? item.question_type
        : 'TEXTAREA') as VersionQuestionForm['question_type'],
      response_mode: item.response_mode || '',
      render_component: item.render_component || '',
      max_score: String(item.max_score || 1),
      grading_engine_code: item.grading_engine_code || '',
      comparison_method: item.comparison_method || '',
      expected_answer_text: '',
      status: item.status || 'ACTIVE',
      required: item.required !== false,
      mcq_options_text: Array.isArray(item.mcq_options) ? item.mcq_options.join('\n') : '',
    });
    setQuestionMessage('Đang chỉnh sửa câu hỏi đã chọn.');
    setQuestionError(null);
  }

  function buildQuestionPayload(draft: VersionQuestionForm) {
    return {
      question_no: Math.max(1, Number(draft.question_no || 1)),
      question_title: draft.question_title.trim(),
      prompt_text: draft.prompt_text.trim(),
      question_type: draft.question_type,
      response_mode: draft.response_mode.trim(),
      render_component: draft.render_component.trim(),
      max_score: Math.max(0.01, Number(draft.max_score || 1)),
      grading_engine_code: draft.grading_engine_code.trim(),
      comparison_method: draft.comparison_method.trim(),
      expected_answer_text: draft.expected_answer_text.trim() || undefined,
      status: draft.status,
      required: Boolean(draft.required),
      mcq_options:
        draft.question_type === 'MCQ_SINGLE'
          ? draft.mcq_options_text
              .split('\n')
              .map((line) => line.trim())
              .filter((line) => line.length > 0)
          : undefined,
    } as const;
  }

  async function saveQuestionDraft(draft: VersionQuestionForm): Promise<QuestionDraftSaveResult> {
    if (!selectedExamVersionId) {
      return { ok: false, error: questionVersionMissingMessage };
    }
    const payload = buildQuestionPayload(draft);
    const response = draft.question_template_id
      ? await updateExamVersionQuestion(selectedExamVersionId, Number(draft.question_template_id), payload)
      : await createExamVersionQuestion(selectedExamVersionId, payload);
    if (!response.ok) {
      return { ok: false, error: normalizeQuestionErrorMessage(response.error.message) };
    }
    await loadVersionQuestions(selectedExamVersionId);
    await loadVersionProfiles(selectedExamVersionId);
    return {
      ok: true,
      message: draft.question_template_id ? 'Đã cập nhật câu hỏi.' : 'Đã tạo câu hỏi.',
    };
  }

  async function handleQuestionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQuestionError(null);
    setQuestionMessage(null);

    const existingQuestionNos = new Set(
      versionQuestions
        .map((item) => Number(item.question_no))
        .filter((value) => Number.isFinite(value) && value > 0)
    );
    let ignoreQuestionNo: number | undefined;
    if (questionForm.question_template_id) {
      const editingItem = versionQuestions.find(
        (item) => String(item.question_template_id) === String(questionForm.question_template_id)
      );
      if (editingItem) {
        ignoreQuestionNo = Number(editingItem.question_no);
      }
    }
    const validationError = validateQuestionDraftForUx(questionForm, existingQuestionNos, { ignoreQuestionNo });
    if (validationError) {
      setQuestionError(validationError);
      return;
    }

    setQuestionSubmitting(true);

    const result = await saveQuestionDraft(questionForm);

    setQuestionSubmitting(false);
    if (!result.ok) {
      setQuestionError(result.error || 'Không thể lưu câu hỏi. Vui lòng thử lại.');
      return;
    }

    setQuestionMessage(result.message || 'Đã lưu câu hỏi.');
    setQuestionForm((current) => ({
      ...initialVersionQuestionForm,
      question_no: String(Math.max(1, Number(current.question_no || 1)) + 1),
    }));
  }

  async function handleCreateSitting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSittingId && !sittingForm.exam_version_id) {
      setSittingError('Cần chọn exam version.');
      return;
    }

    setSittingSubmitting(true);
    setSittingError(null);
    setSittingMessage(null);

    const response = selectedSittingId
      ? await updateDeliverySitting(selectedSittingId, {
          sitting_name: sittingForm.sitting_name.trim(),
          scheduled_start_at: toIsoDateTime(sittingForm.scheduled_start_at),
          scheduled_end_at: toIsoDateTime(sittingForm.scheduled_end_at),
        })
      : await createDeliverySitting({
          sitting_code: sittingForm.sitting_code.trim(),
          sitting_name: sittingForm.sitting_name.trim(),
          exam_version_id: Number(sittingForm.exam_version_id),
          scheduled_start_at: toIsoDateTime(sittingForm.scheduled_start_at),
          scheduled_end_at: toIsoDateTime(sittingForm.scheduled_end_at),
          status: sittingForm.status,
        });

    setSittingSubmitting(false);
    if (!response.ok) {
      const rawMessage = String(response.error.message || '');
      if (/request validation failed/i.test(rawMessage)) {
        setSittingError('Không tạo được ca thi. Dữ liệu gửi lên chưa đúng định dạng API.');
      } else {
        setSittingError(rawMessage);
      }
      console.error('Create sitting validation error', response.error);
      return;
    }

    setSittingForm((current) => ({
      ...initialSittingForm,
      exam_version_id: current.exam_version_id,
    }));
    setSittingMessage(selectedSittingId ? 'Đã cập nhật thông tin ca thi.' : 'Đã tạo ca thi.');
    await loadSittings();
  }

  async function handleAssignSittingExamVersion(examVersionId: string) {
    if (!selectedSittingId) {
      setSittingError('Vui lòng chọn hoặc tạo ca thi trước.');
      return;
    }
    if (sittingVersionIsLocked(selectedSitting)) {
      setSittingError(
        `Ca thi đang ở trạng thái ${asString(selectedSitting?.sitting_status)} nên không thể đổi phiên bản đề áp dụng. Hãy gắn phiên bản khi ca thi còn DRAFT hoặc tạo ca thi mới.`
      );
      return;
    }
    if (!examVersionId) {
      setSittingError('Ca thi chưa gắn phiên bản đề. Vui lòng chọn phiên bản đề áp dụng.');
      return;
    }
    setSittingSubmitting(true);
    setSittingError(null);
    setSittingMessage(null);
    const response = await assignSittingExamVersion(selectedSittingId, { exam_version_id: Number(examVersionId) });
    setSittingSubmitting(false);
    if (!response.ok) {
      setSittingError(response.error.message);
      return;
    }
    setSittingMessage('Đã gắn phiên bản đề cho ca thi.');
    await loadSittings();
    setSittingReadinessStale(true);
    await refreshSittingReadiness();
  }

  async function handleChangeSittingStatus(status: string) {
    if (!selectedSittingId) {
      setPublishError('Vui lòng chọn hoặc tạo ca thi trước.');
      return;
    }
    if (publishSubmitting) {
      return;
    }
    setPublishSubmitting(true);
    setPublishError(null);
    setPublishMessage(null);
    const response = await changeExamSittingStatus(selectedSittingId, status);
    setPublishSubmitting(false);
    if (!response.ok) {
      setPublishError(response.error.message);
      return;
    }
    const nextStatus = String(response.data.sitting_status || status).toUpperCase();
    setSittings((current) =>
      current.map((item) =>
        String(item.exam_sitting_id) === selectedSittingId
          ? { ...item, ...response.data, sitting_status: nextStatus }
          : item
      )
    );
    setSittingForm((current) => ({ ...current, status: nextStatus }));
    setPublishMessage(status === 'OPEN' ? 'Đã mở ca thi cho sinh viên.' : `Đã chuyển ca thi sang ${status}.`);
    setSittingReadinessStale(true);
    await refreshSittingReadiness();
  }

  async function handlePrepareSittingRuntime() {
    if (!selectedSittingId) {
      setPublishError('Vui lòng chọn hoặc tạo ca thi trước.');
      return;
    }
    if (publishSubmitting) {
      return;
    }
    setPublishSubmitting(true);
    setPublishError(null);
    setPublishMessage(null);
    const response = await prepareExamSittingRuntime(selectedSittingId);
    setPublishSubmitting(false);
    if (!response.ok) {
      setPublishError(response.error.message);
      return;
    }
    setPublishMessage(
      `Đã chuẩn bị runtime: ${response.data.created_session_count} session mới, ${response.data.reused_session_count} session đã có, ${response.data.created_generated_question_count} câu hỏi runtime.`
    );
    setSittingReadinessStale(true);
    await loadSittings();
    await refreshSittingReadiness();
  }

  async function handleCreateSittingRoom(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSittingId) {
      setRoomError('Vui lòng chọn hoặc tạo ca thi trước.');
      return;
    }
    if (!sittingRoomForm.room_id) {
      setRoomError('Vui lòng chọn phòng thi trong danh mục phòng.');
      return;
    }
    setRoomSubmitting(true);
    setRoomError(null);
    setRoomMessage(null);
    const response = editingSittingRoomId
      ? await updateSittingRoom(Number(editingSittingRoomId), {
          capacity_allocated: sittingRoomForm.capacity_allocated ? Number(sittingRoomForm.capacity_allocated) : null,
          room_status: sittingRoomForm.room_status,
        })
      : await createSittingRoom(Number(selectedSittingId), {
          room_id: Number(sittingRoomForm.room_id),
          capacity_allocated: sittingRoomForm.capacity_allocated ? Number(sittingRoomForm.capacity_allocated) : null,
          room_status: sittingRoomForm.room_status,
        });
    setRoomSubmitting(false);
    if (!response.ok) {
      setRoomError(response.error.message);
      return;
    }
    setRoomMessage(editingSittingRoomId ? 'Đã cập nhật phòng thi.' : 'Đã thêm phòng thi vào ca.');
    resetSittingRoomForm();
    await loadSittingData(Number(selectedSittingId));
  }

  function handleEditSittingRoom(room: DeliverySittingRoom) {
    setEditingSittingRoomId(String(room.exam_sitting_room_id));
    setSittingRoomForm({
      room_id: String(room.room_id ?? ''),
      capacity_allocated: room.capacity_allocated != null ? String(room.capacity_allocated) : '',
      room_status: room.room_status || 'PLANNED',
    });
  }

  function resetSittingRoomForm() {
    setEditingSittingRoomId('');
    setSittingRoomForm(initialSittingRoomForm);
  }

  async function handleCancelSittingRoom(examSittingRoomId: number) {
    setRoomSubmitting(true);
    setRoomError(null);
    const response = await cancelSittingRoom(examSittingRoomId);
    setRoomSubmitting(false);
    if (!response.ok) {
      setRoomError(response.error.message);
      return;
    }
    setRoomMessage('Đã hủy phòng thi trong ca.');
    resetSittingRoomForm();
    if (selectedSittingId) {
      await loadSittingData(Number(selectedSittingId));
    }
  }

  async function handleCreateProctor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSittingId) {
      setProctorError('Vui lòng chọn hoặc tạo ca thi trước.');
      return;
    }
    if (!proctorForm.exam_sitting_room_id) {
      setProctorError('Ca thi chưa có phòng thi. Hãy thêm phòng thi trước khi gắn giám thị.');
      return;
    }
    if (!proctorForm.proctor_user_id) {
      setProctorError('Vui lòng chọn giám thị.');
      return;
    }
    setProctorSubmitting(true);
    setProctorError(null);
    setProctorMessage(null);
    const response = editingProctorId
      ? await updateRoomProctor(Number(editingProctorId), {
          proctor_role: proctorForm.proctor_role,
          status: proctorForm.status,
        })
      : await createRoomProctor(Number(proctorForm.exam_sitting_room_id), {
          proctor_user_id: Number(proctorForm.proctor_user_id),
          proctor_role: proctorForm.proctor_role,
          status: proctorForm.status,
        });
    setProctorSubmitting(false);
    if (!response.ok) {
      setProctorError(response.error.message);
      return;
    }
    setProctorMessage(editingProctorId ? 'Đã cập nhật giám thị.' : 'Đã gán giám thị.');
    resetProctorForm();
    await loadRoomProctors(Number(proctorForm.exam_sitting_room_id));
  }

  function handleEditProctor(assignment: DeliveryProctorAssignment) {
    setEditingProctorId(String(assignment.proctor_assignment_id));
    setProctorForm({
      exam_sitting_room_id: String(assignment.exam_sitting_room_id),
      proctor_user_id: String(assignment.proctor_user_id),
      proctor_role: assignment.proctor_role || 'ROOM_PROCTOR',
      status: assignment.status || 'ASSIGNED',
    });
  }

  function resetProctorForm() {
    setEditingProctorId('');
    setProctorForm(initialProctorForm);
  }

  async function handleCancelProctor(proctorAssignmentId: number) {
    setProctorSubmitting(true);
    setProctorError(null);
    const response = await cancelRoomProctor(proctorAssignmentId);
    setProctorSubmitting(false);
    if (!response.ok) {
      setProctorError(response.error.message);
      return;
    }
    setProctorMessage('Đã hủy phân công giám thị.');
    resetProctorForm();
    if (proctorForm.exam_sitting_room_id) {
      await loadRoomProctors(Number(proctorForm.exam_sitting_room_id));
    }
  }

  async function handleCreateAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSittingId) {
      setAssignmentError('Vui lòng chọn hoặc tạo ca thi trước.');
      return;
    }
    if (!assignmentForm.student_id) {
      setAssignmentError('Vui lòng chọn thí sinh hoặc dùng import theo mã sinh viên.');
      return;
    }
    setAssignmentSubmitting(true);
    setAssignmentError(null);
    setAssignmentMessage(null);
    const response = editingAssignmentId
      ? await updateExamAssignment(Number(editingAssignmentId), {
          assignment_status: assignmentForm.assignment_status,
          note: assignmentForm.note || null,
        })
      : await createExamAssignment(Number(selectedSittingId), {
          student_id: Number(assignmentForm.student_id),
          assignment_status: assignmentForm.assignment_status,
          note: assignmentForm.note || null,
        });
    setAssignmentSubmitting(false);
    if (!response.ok) {
      setAssignmentError(response.error.message);
      return;
    }
    setAssignmentMessage(editingAssignmentId ? 'Đã cập nhật thí sinh dự thi.' : 'Đã thêm thí sinh vào ca thi.');
    resetAssignmentForm();
    await loadSittingData(Number(selectedSittingId));
  }

  function parseAssignmentImportRows(): Array<{ sitting_code: string; student_code: string; note?: string | null }> {
    return assignmentImportForm.rows_text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .map((line) => {
        const [studentCodeRaw, sittingCodeRaw, noteRaw] = line.split(/[,\t;]/).map((part) => part.trim());
        return {
          student_code: studentCodeRaw,
          sitting_code: sittingCodeRaw || selectedSitting?.sitting_code || '',
          note: noteRaw || assignmentImportForm.note || null,
        };
      });
  }

  async function handleImportAssignments(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSittingId || !selectedSitting) {
      setAssignmentError('Vui lòng chọn hoặc tạo ca thi trước.');
      return;
    }
    const items = parseAssignmentImportRows();
    if (!items.length || items.some((item) => !item.student_code || !item.sitting_code)) {
      setAssignmentError('Mỗi dòng import cần có mã sinh viên và mã ca thi.');
      return;
    }
    setAssignmentSubmitting(true);
    setAssignmentError(null);
    setAssignmentMessage(null);
    const response = await importExamAssignmentsByCode({
      assignment_status: assignmentImportForm.assignment_status,
      items,
    });
    setAssignmentSubmitting(false);
    if (!response.ok) {
      setAssignmentError(response.error.message);
      return;
    }
    const created = Number(response.data.created_count || 0);
    const failed = Number(response.data.error_count || 0);
    setAssignmentMessage(`Đã import ${created} sinh viên vào ca thi${failed ? `, ${failed} dòng lỗi` : ''}.`);
    if (failed) {
      setAssignmentError(
        response.data.errors
          .slice(0, 5)
          .map((item) => `${asString(item.student_code)}: ${asString(item.message, asString(item.code))}`)
          .join('; ')
      );
    }
    setAssignmentImportForm((current) => ({ ...current, rows_text: failed ? current.rows_text : '' }));
    await loadSittingData(Number(selectedSittingId));
  }

  function handleEditAssignment(assignment: DeliveryExamAssignment) {
    setEditingAssignmentId(String(assignment.exam_assignment_id));
    setAssignmentForm({
      student_id: String(assignment.student_id),
      assignment_status: assignment.assignment_status || 'ASSIGNED',
      note: assignment.note || '',
    });
  }

  function resetAssignmentForm() {
    setEditingAssignmentId('');
    setAssignmentForm(initialAssignmentForm);
  }

  async function handleDeactivateAssignment(assignment: DeliveryExamAssignment) {
    setAssignmentSubmitting(true);
    setAssignmentError(null);
    const response = await updateExamAssignment(Number(assignment.exam_assignment_id), {
      assignment_status: 'CANCELLED',
      note: assignment.note || null,
    });
    setAssignmentSubmitting(false);
    if (!response.ok) {
      setAssignmentError(response.error.message);
      return;
    }
    setAssignmentMessage('Đã hủy thí sinh khỏi ca thi.');
    resetAssignmentForm();
    if (selectedSittingId) {
      await loadSittingData(Number(selectedSittingId));
    }
  }

  async function handleCreateStationAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSittingId) {
      setSeatingError('Vui lòng chọn hoặc tạo ca thi trước.');
      return;
    }
    if (!stationAssignmentForm.exam_assignment_id) {
      setSeatingError('Ca thi chưa có sinh viên dự thi. Hãy import hoặc thêm sinh viên trước khi xếp máy.');
      return;
    }
    if (!stationAssignmentForm.exam_sitting_room_id) {
      setSeatingError('Ca thi chưa có phòng thi. Hãy thêm phòng thi trước khi xếp máy.');
      return;
    }
    if (!stationAssignmentForm.station_id) {
      setSeatingError('Vui lòng chọn vị trí máy.');
      return;
    }
    setSeatingSubmitting(true);
    setSeatingError(null);
    setSeatingMessage(null);
    const payload = {
      station_id: Number(stationAssignmentForm.station_id),
      planned_device_id: stationAssignmentForm.planned_device_id ? Number(stationAssignmentForm.planned_device_id) : null,
      status: stationAssignmentForm.status,
    };
    const response = editingStationAssignmentId
      ? await updateExamStationAssignment(Number(editingStationAssignmentId), payload)
      : await assignExamStation(Number(stationAssignmentForm.exam_assignment_id), {
          exam_sitting_room_id: Number(stationAssignmentForm.exam_sitting_room_id),
          ...payload,
        });
    setSeatingSubmitting(false);
    if (!response.ok) {
      setSeatingError(response.error.message);
      return;
    }
    setSeatingMessage(editingStationAssignmentId ? 'Đã cập nhật chỗ ngồi.' : 'Đã gán chỗ.');
    resetStationAssignmentForm();
    await loadSittingData(Number(selectedSittingId));
  }

  async function handleAutoAssignStations() {
    if (!selectedSittingId) {
      setSeatingError('Vui lòng chọn hoặc tạo ca thi trước.');
      return;
    }
    if (!stationAssignmentForm.exam_sitting_room_id) {
      setSeatingError('Vui lòng chọn phòng thi trước khi gán tự động.');
      return;
    }

    const selectedRoom = sittingRooms.find(
      (room) => String(room.exam_sitting_room_id) === String(stationAssignmentForm.exam_sitting_room_id)
    );
    if (!selectedRoom) {
      setSeatingError('Phòng thi đã chọn không còn hợp lệ. Vui lòng chọn lại phòng thi.');
      return;
    }

    const occupiedAssignmentIds = new Set(seatingPlan.map((item) => String(item.exam_assignment_id)));
    const occupiedStationIds = new Set(seatingPlan.map((item) => String(item.station_id)));
    const unassignedStudents = assignments
      .filter((assignment) => !['CANCELLED', 'VOIDED'].includes(String(assignment.assignment_status || '').toUpperCase()))
      .filter((assignment) => !occupiedAssignmentIds.has(String(assignment.exam_assignment_id)))
      .sort((a, b) => Number(a.exam_assignment_id) - Number(b.exam_assignment_id));
    const availableStations = sortByStationCode(
      selectedRoomStations
        .filter((station) => {
          const stationRoomId = station.room_id == null ? '' : String(station.room_id);
          const stationRoomCode = String(station.room_code || '');
          return !stationRoomId || stationRoomId === String(selectedRoom.room_id) || stationRoomCode === String(selectedRoom.room_code || '');
        })
        .filter((station) => !occupiedStationIds.has(getId(station, 'station_id'))) as Array<{ station_code?: string | null }>
    ) as ExamSetupRow[];

    if (unassignedStudents.length === 0) {
      setSeatingError('Không còn sinh viên chưa được xếp máy trong ca thi này.');
      return;
    }
    if (availableStations.length === 0) {
      setSeatingError('Phòng thi đã chọn không còn máy trống để gán.');
      return;
    }

    setSeatingSubmitting(true);
    setSeatingError(null);
    setSeatingMessage(null);
    const pairCount = Math.min(unassignedStudents.length, availableStations.length);
    let assignedCount = 0;

    for (let index = 0; index < pairCount; index += 1) {
      const assignment = unassignedStudents[index];
      const station = availableStations[index];
      const response = await assignExamStation(Number(assignment.exam_assignment_id), {
        exam_sitting_room_id: Number(stationAssignmentForm.exam_sitting_room_id),
        station_id: Number(getId(station, 'station_id')),
        planned_device_id: null,
        status: 'ASSIGNED',
      });
      if (!response.ok) {
        setSeatingSubmitting(false);
        setSeatingError(`Gán tự động dừng tại ${asString(assignment.student_code, `thí sinh #${assignment.exam_assignment_id}`)}: ${response.error.message}`);
        if (assignedCount > 0) {
          await loadSittingData(Number(selectedSittingId));
        }
        return;
      }
      assignedCount += 1;
    }

    setSeatingSubmitting(false);
    setSeatingMessage(
      assignedCount < unassignedStudents.length
        ? `Đã gán tự động ${assignedCount}/${unassignedStudents.length} sinh viên. Phòng thi đã hết máy trống.`
        : `Đã gán tự động ${assignedCount} sinh viên.`
    );
    resetStationAssignmentForm();
    await loadSittingData(Number(selectedSittingId));
  }

  function handleEditStationAssignment(assignment: DeliveryStationAssignment) {
    setEditingStationAssignmentId(String(assignment.station_assignment_id));
    setStationAssignmentForm({
      exam_assignment_id: String(assignment.exam_assignment_id),
      exam_sitting_room_id: String(assignment.exam_sitting_room_id),
      station_id: String(assignment.station_id),
      planned_device_id: assignment.planned_device_id != null ? String(assignment.planned_device_id) : '',
      status: assignment.status || 'ASSIGNED',
    });
  }

  function resetStationAssignmentForm() {
    setEditingStationAssignmentId('');
    setStationAssignmentForm(initialStationAssignmentForm);
  }

  async function handleDeactivateStationAssignment(assignment: DeliveryStationAssignment) {
    setSeatingSubmitting(true);
    setSeatingError(null);
    const response = await updateExamStationAssignment(Number(assignment.station_assignment_id), {
      station_id: Number(assignment.station_id),
      planned_device_id: assignment.planned_device_id ?? null,
      status: 'CANCELLED',
    });
    setSeatingSubmitting(false);
    if (!response.ok) {
      setSeatingError(response.error.message);
      return;
    }
    setSeatingMessage('Đã hủy chỗ ngồi.');
    resetStationAssignmentForm();
    if (selectedSittingId) {
      await loadSittingData(Number(selectedSittingId));
    }
  }

  return (
    <CompactPage className="exam-setup-page" data-testid={testId}>
      <CompactPageHeader
        eyebrow={surfaceEyebrow}
        title={surfaceTitle}
        description={surfaceDescription}
        primaryActions={
          <IconActionButton
            icon="refresh"
            variant="ghost-button"
            label="Tải lại API"
            onClick={() => {
              void loadBaseData();
              void loadSittings();
            }}
          />
        }
      />

      <CompactToolbar data-testid="exam-setup-compact-toolbar">
        {showApiDiagnostics ? <ApiCoverageBadge status={activeSection.apiStatus} /> : null}
        <span className="muted">Workflow: {asString(activeSection.title, 'N/A')}</span>
        <span className="muted">Blueprint: {selectedExamId || 'chưa chọn'}</span>
        <span className="muted">Version: {selectedExamVersionId || 'chưa chọn'}</span>
        <span className="muted">Sitting: {selectedSittingId || 'chưa chọn'}</span>
      </CompactToolbar>

      <CompactStatBar
        items={[
          { label: 'Exam status', value: selectedExamStatus },
          { label: 'Version status', value: asString(snapshot.examVersions.find((v) => getId(v, 'exam_version_id') === selectedExamVersionId)?.status, '-') },
          { label: 'Sitting status', value: asString(selectedSitting?.sitting_status, '-') },
          {
            label: 'Readiness',
            value: sittingReadinessLoading
              ? 'Đang tải'
              : sittingReadiness?.ready
                ? 'READY'
                : selectedSittingId
                  ? 'BLOCKED'
                  : '-',
          },
        ]}
      />

      {snapshot.error ? <p className="form-error">{snapshot.error}</p> : null}
      {snapshot.loading ? <p className="muted">Đang tải dữ liệu API...</p> : null}

      {visibleSectionGroups.some((group) => group.keys.includes('sittings')) ? (
        <CompactSurface tight>
          <WorkflowContextPanel
            selectedSitting={selectedSitting}
            appliedExamVersionId={appliedExamVersionId}
            appliedVersion={appliedVersion}
            versionQuestions={appliedVersionQuestions}
            questionReadiness={appliedQuestionReadiness}
            sittingRooms={sittingRooms}
            assignments={assignments}
            seatingPlan={seatingPlan}
            proctors={proctors}
          />
        </CompactSurface>
      ) : null}

      {visibleSectionGroups.length > 1 ? (
        <CompactSurface tight>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 'var(--sp-2)',
            padding: 'var(--sp-3) var(--sp-4)',
            background: 'var(--surface-card)',
            border: '1px solid var(--clr-gray-200)',
            borderRadius: 'var(--radius-lg)',
            marginBottom: 'var(--sp-4)',
          }}
        >
          {[
            {
              key: 'A',
              title: 'Bước A: Soạn đề (Authoring)',
              desc: 'Từ đề gốc đến phiên bản đề & câu hỏi',
              keys: authoringSectionKeys,
            },
            {
              key: 'B',
              title: 'Bước B: Cấu hình ca thi (Context)',
              desc: 'Lập ca, gán sinh viên, phòng thi, xếp máy & giám thị',
              keys: ['sittings', 'sitting-version', 'assignments', 'rooms', 'seating', 'proctors'] as SetupSectionKey[],
            },
            {
              key: 'C',
              title: 'Bước C: Kiểm tra & Phát hành',
              desc: 'Rà soát độ sẵn sàng & mở ca thi',
              keys: ['readiness', 'publish'] as SetupSectionKey[],
            },
          ]
            .filter((step) => step.keys.some((stepKey) => visibleSections.some((section) => section.key === stepKey)))
            .map((step) => {
              const isActive = step.keys.includes(activeKey);
              return (
                <div
                  key={step.key}
                  style={{
                    flex: 1,
                    padding: 'var(--sp-2) var(--sp-3)',
                    borderRadius: 'var(--radius-md)',
                    background: isActive ? 'var(--clr-primary-50)' : 'transparent',
                    border: isActive ? '1px solid var(--clr-primary-200)' : '1px solid transparent',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--sp-2)',
                  }}
                >
                  <div
                    style={{
                      width: '28px',
                      height: '28px',
                      borderRadius: '50%',
                      background: isActive ? 'var(--clr-primary-600)' : 'var(--clr-gray-200)',
                      color: isActive ? '#fff' : 'var(--text-secondary)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 'var(--fw-bold)',
                      fontSize: 'var(--text-xs)',
                    }}
                  >
                    {step.key}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
                    <span style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--fw-bold)', color: isActive ? 'var(--clr-primary-800)' : 'var(--text-primary)' }}>
                      {step.title}
                    </span>
                    <span style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>{step.desc}</span>
                  </div>
                </div>
              );
            })}
        </div>
        </CompactSurface>
      ) : null}

      <CompactSurface tight>
      <div className="master-data-layout setup-layout">
        <aside className="master-data-sidebar" aria-label="Các bước thiết lập ca thi">
          {visibleSectionGroups.map((group) => (
            <div key={group.heading}>
              <span className="setup-sidebar-heading">{group.heading}</span>
              {group.sections.map((section) => (
                <button
                  className={section.key === activeKey ? 'master-data-tab is-active' : 'master-data-tab'}
                  key={section.key}
                  type="button"
                  onClick={() => setActiveKey(section.key)}
                >
                  {section.title}
                </button>
              ))}
            </div>
          ))}
          <ApiCoverageBadge status={activeSection.apiStatus} />
        </aside>
        {renderSection(activeKey, snapshot, {
            onSelect: setActiveKey,
            selectedExamId,
            selectedExamVersionId,
            examForm,
            examSubmitting,
            examMessage,
            examError,
            versionForm,
            versionSubmitting,
            versionMessage,
            versionError,
            versionPublishing,
            versionPublishMessage,
            versionPublishError,
            versionPublishBlockers,
            examActivationLoading,
            paperAssets,
            paperAssetsLoading,
            paperSubmitting,
            paperMessage,
            paperError,
            deliveryProfile,
            deliveryContentType,
            gradingProfiles,
            profileLoading,
            profileSubmitting,
            profileMessage,
            profileError,
            versionQuestions,
            questionReadiness,
            questionForm,
            questionSubmitting,
            questionMessage,
            questionError,
            sittings,
            selectedSittingId,
            selectedSitting,
            appliedExamVersionId,
            appliedVersion,
            appliedVersionQuestions,
            appliedQuestionReadiness,
            sittingReadiness,
            sittingReadinessLoading,
            sittingReadinessError,
            sittingReadinessStale,
            sittingRooms,
            proctors,
            assignments,
            seatingPlan,
            selectedRoomStations,
            selectedRoomStationsLoading,
            sittingForm,
            sittingRoomForm,
            proctorForm,
            assignmentForm,
            assignmentImportForm,
            stationAssignmentForm,
            editingSittingRoomId,
            editingProctorId,
            editingAssignmentId,
            editingStationAssignmentId,
            sittingSubmitting,
            sittingMessage,
            sittingError,
            roomSubmitting,
            roomMessage,
            roomError,
            proctorSubmitting,
            proctorMessage,
            proctorError,
            assignmentSubmitting,
            assignmentMessage,
            assignmentError,
            seatingSubmitting,
            seatingMessage,
            seatingError,
            publishSubmitting,
            publishMessage,
            publishError,
            onSelectExam: setSelectedExamId,
            onSelectExamVersion: setSelectedExamVersionId,
            onExamFormChange: (patch) => setExamForm((current) => ({ ...current, ...patch })),
            onExamSubmit: (event) => void handleCreateExam(event),
            onVersionFormChange: (patch) => setVersionForm((current) => ({ ...current, ...patch })),
            onVersionSubmit: (event) => void handleCreateVersion(event),
            onPublishVersion: handlePublishVersion,
            onActivateExamBlueprint: handleActivateExamBlueprint,
            onUploadPaperAsset: handleUploadPaperAsset,
            onRetirePaperAsset: handleRetirePaperAsset,
            onDeliveryContentTypeChange: setDeliveryContentType,
            onSaveDeliveryContentType: handleSaveDeliveryContentType,
            onConfigureFileUploadManualGrading: handleConfigureFileUploadManualGrading,
            onApplyFileUploadPreset: handleApplyFileUploadPreset,
            onCreatePlaceholderQuestion: handleCreatePlaceholderQuestion,
            onRetireGradingProfile: handleRetireGradingProfile,
            onQuestionFormChange: (patch) => setQuestionForm((current) => ({ ...current, ...patch })),
            onQuestionTypeChange: handleQuestionTypeChange,
            onQuestionSubmit: (event) => void handleQuestionSubmit(event),
            onQuestionSaveDraft: saveQuestionDraft,
            onQuestionEdit: handleQuestionEdit,
            onSittingFormChange: (patch) => setSittingForm((current) => ({ ...current, ...patch })),
            onSittingSubmit: (event) => void handleCreateSitting(event),
            onSittingSelect: setSelectedSittingId,
            onNewSitting: () => {
              setSelectedSittingId('');
              setSittingForm((current) => ({ ...initialSittingForm, exam_version_id: current.exam_version_id || selectedExamVersionId }));
            },
            onAssignSittingExamVersion: handleAssignSittingExamVersion,
            onSittingRoomFormChange: (patch) => setSittingRoomForm((current) => ({ ...current, ...patch })),
            onSittingRoomCreate: (event) => void handleCreateSittingRoom(event),
            onSittingRoomEdit: handleEditSittingRoom,
            onSittingRoomCancel: handleCancelSittingRoom,
            onNewSittingRoom: resetSittingRoomForm,
            onProctorFormChange: (patch) => setProctorForm((current) => ({ ...current, ...patch })),
            onProctorCreate: (event) => void handleCreateProctor(event),
            onProctorEdit: handleEditProctor,
            onProctorCancel: handleCancelProctor,
            onNewProctor: resetProctorForm,
            onAssignmentFormChange: (patch) => setAssignmentForm((current) => ({ ...current, ...patch })),
            onAssignmentImportFormChange: (patch) => setAssignmentImportForm((current) => ({ ...current, ...patch })),
            onAssignmentCreate: (event) => void handleCreateAssignment(event),
            onAssignmentImport: (event) => void handleImportAssignments(event),
            onAssignmentEdit: handleEditAssignment,
            onAssignmentDeactivate: handleDeactivateAssignment,
            onNewAssignment: resetAssignmentForm,
            onStationAssignmentFormChange: (patch) => setStationAssignmentForm((current) => ({ ...current, ...patch })),
            onStationAssignmentCreate: (event) => void handleCreateStationAssignment(event),
            onStationAssignmentAutoAssign: handleAutoAssignStations,
            onStationAssignmentEdit: handleEditStationAssignment,
            onStationAssignmentDeactivate: handleDeactivateStationAssignment,
            onNewStationAssignment: resetStationAssignmentForm,
            onSittingRuntimePrepare: handlePrepareSittingRuntime,
            onSittingStatusChange: handleChangeSittingStatus,
            onRefreshSittingReadiness: refreshSittingReadiness,
            sittingClassSections,
            classSectionDraft,
            classSectionLoading,
            classSectionSubmitting,
            classSectionMessage,
            classSectionError,
            classSectionImporting,
            onClassSectionToggle: (id: number) => {
              setClassSectionDraft((prev) => {
                const next = new Set(prev);
                if (next.has(id)) {
                  next.delete(id);
                } else {
                  next.add(id);
                }
                return next;
              });
              setClassSectionMessage(null);
            },
            onClassSectionSave: async () => {
              if (!selectedSittingId) return;
              setClassSectionSubmitting(true);
              setClassSectionMessage(null);
              setClassSectionError(null);
              try {
                const payload: SittingClassSectionsUpdatePayload = {
                  class_section_ids: Array.from(classSectionDraft),
                };
                const response = await updateSittingClassSections(Number(selectedSittingId), payload);
                if (!response.ok) {
                  setClassSectionError(response.error.message);
                } else {
                  const saved = response.data.items ?? [];
                  setSittingClassSections(saved);
                  setClassSectionDraft(new Set(saved.map((r) => r.class_section_id)));
                  setClassSectionMessage('Đã lưu lớp học phần cho ca thi.');
                }
              } catch (err) {
                setClassSectionError(err instanceof Error ? err.message : 'Lưu thất bại.');
              } finally {
                setClassSectionSubmitting(false);
              }
            },
            onClassSectionImport: async () => {
              if (!selectedSittingId) return;
              setClassSectionImporting(true);
              setClassSectionMessage(null);
              setClassSectionError(null);
              try {
                const response = await importAssignmentsFromClassSections(Number(selectedSittingId));
                if (!response.ok) {
                  setClassSectionError(response.error.message);
                } else {
                  const created = response.data.created_count ?? 0;
                  setClassSectionMessage(`Đã nạp ${created} sinh viên từ các lớp đã chọn vào ca thi.`);
                  await loadSittingData(Number(selectedSittingId));
                }
              } catch (err) {
                setClassSectionError(err instanceof Error ? err.message : 'Nạp sinh viên thất bại.');
              } finally {
                setClassSectionImporting(false);
              }
            },
          })}
      </div>
      </CompactSurface>
    </CompactPage>
  );
}
