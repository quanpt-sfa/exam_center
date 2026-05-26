import { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  autosaveAnswers,
  bindExamDevice,
  getExamRuntimePayload,
  getSealPreflight,
  loadAnswerState,
  loadExamSessionPaperAssets,
  sendHeartbeat,
  sealSubmission,
  startExamSessionStrict,
  uploadAnswerFile,
} from './api';
import type {
  AutosaveAnswerDraft,
  ExamQuestion,
  ExamSessionPaperAsset,
  ExamTakingPayload,
  QuestionFileMetadata,
  SealPreflightResponse,
} from './types';
import { isEditableTextMode, isFileUploadMode, normalizeAnswerMode } from './contracts';
import { VisualPaperViewer } from './VisualPaperViewer';
import { ExamTakerIdentityPanel } from './ExamTakerIdentityPanel';

type AutosaveStatus = 'idle' | 'dirty' | 'saving' | 'saved' | 'unsynced' | 'failed';
type QuestionRenderMode = 'TEXT' | 'FILE_UPLOAD' | 'INSTRUCTION_ONLY' | 'UNSUPPORTED';
type RuntimePageState =
  | 'loading_runtime'
  | 'runtime_error'
  | 'requires_device_binding'
  | 'ready_to_start'
  | 'starting'
  | 'in_progress'
  | 'heartbeat_degraded'
  | 'sealed'
  | 'closed_or_interrupted'
  | 'unsupported_runtime_mode';
type SubmitPhase = 'idle' | 'checking_preflight' | 'blocked' | 'ready_to_seal' | 'sealing';
type AnswerState = Record<number, string>;
type RevisionState = Record<number, number>;
type QuestionNavigatorTone = 'answered' | 'dirty' | 'missing' | 'file' | 'blocked' | 'unsupported' | 'empty';
type FileState = {
  currentFile: QuestionFileMetadata | null;
  selectedFile: File | null;
  uploading: boolean;
  error: string | null;
};
type FileAnswerState = Record<number, FileState>;
type QuestionUiModel = {
  question: ExamQuestion;
  mode: QuestionRenderMode;
  answerType: string;
  answerLabel: string;
  helperText: string | null;
  isRequired: boolean;
  isAnswered: boolean;
  isDirty: boolean;
  hasUploadedFile: boolean;
  navigatorTone: QuestionNavigatorTone;
  navigatorLabel: string;
};

const AUTOSAVE_DEBOUNCE_MS = 800;
const HEARTBEAT_INTERVAL_MS = 30000;
const TEXT_TYPES = new Set(['TEXT', 'SHORT_TEXT', 'ESSAY', 'SQL_QUERY', 'TEXTBOX_SQL']);
const STARTABLE_SESSION_STATUSES = new Set(['CREATED', 'WAITING_FOR_CHECKIN', 'READY_TO_START', 'PAUSED', 'INTERRUPTED']);
const ACTIVE_SESSION_STATUSES = new Set(['IN_PROGRESS']);
const TERMINAL_SESSION_STATUSES = new Set(['COMPLETED', 'CANCELLED']);

function statusText(status: AutosaveStatus): string {
  if (status === 'dirty') return 'Có thay đổi chưa lưu';
  if (status === 'saving') return 'Đang lưu lên máy chủ';
  if (status === 'saved') return 'Đã lưu lên máy chủ';
  if (status === 'unsynced') return 'Chưa lưu lên máy chủ';
  if (status === 'failed') return 'Lưu thất bại';
  return 'Chưa có thay đổi';
}

function statusDetail(status: AutosaveStatus, isOnline: boolean): string {
  if (status === 'dirty') return 'Câu trả lời trên màn hình đã thay đổi nhưng chưa được máy chủ xác nhận.';
  if (status === 'saving') return 'Đang gửi câu trả lời văn bản tới Backend API.';
  if (status === 'saved') return 'Máy chủ đã xác nhận autosave gần nhất.';
  if (status === 'unsynced') return isOnline ? 'Máy chủ chưa xác nhận autosave gần nhất.' : 'Thiết bị đang offline. Câu trả lời vẫn ở trên màn hình.';
  if (status === 'failed') return 'Autosave không thành công. Không có trạng thái lưu giả được hiển thị.';
  return 'Chưa phát sinh thay đổi văn bản cần autosave.';
}

function makeClientKey(prefix: string): string {
  const random = Math.random().toString(36).slice(2);
  return `${prefix}-${Date.now()}-${random}`;
}

function userSafeError(code: string | undefined, message: string | undefined): string {
  if (code === 'permission_denied') return 'Bạn không có quyền truy cập bài thi này.';
  if (code === 'exam_session_not_found' || code === 'submission_not_found') return 'Không tìm thấy ca thi hoặc bài làm.';
  if (code === 'validation_error' || code === 'invalid_exam_submission_id') return 'Mã ca thi không hợp lệ.';
  if (code === 'database_unavailable') return 'Hệ thống đang tạm thời bận. Vui lòng thử lại sau.';
  if (code === 'network_error') return 'Không kết nối được tới máy chủ.';
  return message || 'Không tải được dữ liệu bài thi.';
}

function examTitle(payload: ExamTakingPayload): string {
  return payload.session.exam_name || payload.session.sitting_name || payload.session.session_code || `Ca thi #${payload.session.exam_session_id}`;
}

function formatRemaining(seconds?: number | null): string {
  if (seconds == null) return '--:--';
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const remainingSeconds = safeSeconds % 60;
  if (hours > 0) {
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
  }
  return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
}

function formatDateTime(value?: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return null;
  return new Intl.DateTimeFormat('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date);
}

function sessionStatusText(status?: string | null): string {
  const normalized = String(status || '').toUpperCase();
  if (normalized === 'CREATED') return 'Mới tạo';
  if (normalized === 'WAITING_FOR_CHECKIN') return 'Chờ check-in';
  if (normalized === 'READY_TO_START') return 'Sẵn sàng bắt đầu';
  if (normalized === 'IN_PROGRESS') return 'Đang làm bài';
  if (normalized === 'PAUSED') return 'Tạm dừng';
  if (normalized === 'INTERRUPTED') return 'Gián đoạn';
  if (normalized === 'COMPLETED') return 'Đã hoàn tất';
  if (normalized === 'CANCELLED') return 'Đã hủy';
  return status || 'Chưa xác định';
}

function submissionStatusText(status?: string | null): string {
  const normalized = String(status || '').toUpperCase();
  if (normalized === 'DRAFT') return 'Đang làm bài';
  if (normalized === 'SUBMITTED') return 'Đã nộp';
  if (normalized === 'SEALED') return 'Đã khóa bài';
  if (normalized === 'GRADED') return 'Đã chấm';
  return status || 'Chưa xác định';
}

function selectActivePaperAsset(items: ExamSessionPaperAsset[]): ExamSessionPaperAsset | null {
  if (!items.length) return null;
  const explicitActive = items.find((asset) => asset.is_active === true && asset.content_url);
  if (explicitActive) return explicitActive;
  return items.find((asset) => Boolean(asset.content_url)) || null;
}

function resolveQuestionAnswerMode(question: ExamQuestion): string {
  const directMode = String(question.answer_ui?.ui_mode || question.response_profile?.ui_mode || '').trim();
  if (directMode) {
    return normalizeAnswerMode(directMode);
  }

  const inputSource = String(question.answer_ui?.input_source || question.response_profile?.input_source || '').trim();
  if (inputSource) {
    return normalizeAnswerMode(inputSource);
  }

  const questionType = String(question.question_type).toUpperCase();
  if (questionType === 'FILE_UPLOAD') return 'FILE_UPLOAD';
  if (questionType.includes('SQL')) return 'SQL_TEXT';
  if (TEXT_TYPES.has(questionType)) return 'TEXT';
  return 'UNSUPPORTED';
}

function renderMode(question: ExamQuestion): QuestionRenderMode {
  const answerMode = resolveQuestionAnswerMode(question);
  if (isFileUploadMode(answerMode)) return 'FILE_UPLOAD';
  if (isEditableTextMode(answerMode)) return 'TEXT';
  if (answerMode === 'INSTRUCTION_ONLY' || answerMode === 'CAPTURE_ONLY') return 'INSTRUCTION_ONLY';
  return 'UNSUPPORTED';
}

function answerTypeForQuestion(question: ExamQuestion): string {
  const answerMode = resolveQuestionAnswerMode(question);
  if (answerMode === 'SQL_TEXT') return 'SQL_TEXT';
  if (answerMode === 'JSON') return 'JSON_TEXT';
  if (answerMode === 'CODE_TEXT') return 'CODE_TEXT';
  return 'TEXT';
}

function answerLabelForQuestion(question: ExamQuestion): string {
  const answerType = answerTypeForQuestion(question);
  if (answerType === 'SQL_TEXT') return 'SQL text answer';
  if (answerType === 'CODE_TEXT') return 'Code text answer';
  if (answerType === 'JSON_TEXT') return 'JSON text answer';
  return 'Text answer';
}

function answerHelperForQuestion(question: ExamQuestion): string | null {
  const answerType = answerTypeForQuestion(question);
  if (answerType === 'SQL_TEXT' || answerType === 'CODE_TEXT' || answerType === 'JSON_TEXT') {
    return 'No execute or run action is available in this phase.';
  }
  return null;
}

function questionRequired(question: ExamQuestion): boolean {
  return question.answer_ui?.required !== false && question.response_profile?.required !== false;
}

function fileFromTakingPayload(question: ExamQuestion): QuestionFileMetadata | null {
  const current = question.answer_ui?.current_file;
  if (!current || typeof current !== 'object') return null;
  if (!Number.isFinite(Number(current.file_asset_id))) return null;
  return {
    file_asset_id: Number(current.file_asset_id),
    original_filename: String(current.original_filename || ''),
    mime_type: String(current.mime_type || ''),
    file_size_bytes: Number(current.file_size_bytes || 0),
    sha256_hash: String(current.sha256_hash || ''),
    uploaded_at: current.uploaded_at ? String(current.uploaded_at) : null,
    status: current.status ? String(current.status) : null,
  };
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function shortHash(hash: string): string {
  const normalized = String(hash || '').trim();
  if (!normalized) return '--';
  return normalized.slice(0, 12);
}

function joinAllowedValues(values?: string[] | null): string {
  if (!values || values.length === 0) return '--';
  return values.join(', ');
}

function initialFileAnswerState(questions: ExamQuestion[]): FileAnswerState {
  const next: FileAnswerState = {};
  questions.forEach((question) => {
    if (renderMode(question) === 'FILE_UPLOAD') {
      next[question.generated_exam_question_id] = {
        currentFile: fileFromTakingPayload(question),
        selectedFile: null,
        uploading: false,
        error: null,
      };
    }
  });
  return next;
}

function applyServerFile(
  current: FileAnswerState,
  questionId: number,
  file: QuestionFileMetadata,
  clearSelected: boolean
): FileAnswerState {
  const base = current[questionId] || {
    currentFile: null,
    selectedFile: null,
    uploading: false,
    error: null,
  };
  return {
    ...current,
    [questionId]: {
      ...base,
      currentFile: file,
      selectedFile: clearSelected ? null : base.selectedFile,
      uploading: false,
      error: null,
    },
  };
}

function sessionStatus(payload: ExamTakingPayload | null): string {
  return String(payload?.session.session_status || '').toUpperCase();
}

function hasActiveDeviceBinding(payload: ExamTakingPayload): boolean {
  const bindingStatus = String(payload.device_binding?.binding_status || payload.device_binding_requirement?.status || '').toUpperCase();
  return bindingStatus === 'ACTIVE' || Boolean(payload.device_binding?.station_id) || Boolean(payload.device_binding?.device_id);
}

function requiresDeviceBinding(payload: ExamTakingPayload): boolean {
  return payload.device_binding_requirement?.required === true;
}

function hasUnsupportedRuntimeOnly(payload: ExamTakingPayload): boolean {
  const modes = payload.paper.questions.map(renderMode);
  if (modes.length === 0) return false;
  return modes.every((mode) => mode === 'UNSUPPORTED');
}

function hasBlockedReadOnlyRuntime(payload: ExamTakingPayload): boolean {
  const readiness = String(
    payload.runtime_contract?.runtime_readiness || payload.delivery_profile?.runtime_readiness || ''
  )
    .trim()
    .toUpperCase();
  const modality = String(payload.runtime_contract?.modality || payload.delivery_profile?.modality || '')
    .trim()
    .toUpperCase();
  const blockerCodes = new Set((payload.blockers || []).map((blocker) => String(blocker.code || '').trim().toUpperCase()));

  if (readiness === 'FOUNDATION_ONLY' || readiness === 'NOT_READY' || readiness === 'UNSUPPORTED') {
    return true;
  }

  if (modality === 'STUDENT_DATABASE' || modality === 'EXTERNAL') {
    return true;
  }

  if (blockerCodes.has('UNSUPPORTED_MODALITY') || blockerCodes.has('RESOURCE_NOT_READY') || blockerCodes.has('CAPTURE_NOT_READY')) {
    return true;
  }

  return false;
}

function hasHardRuntimeBlocker(payload: ExamTakingPayload): boolean {
  return (payload.blockers || []).some((blocker) => {
    const code = String(blocker.code || '').toUpperCase();
    return code.includes('ROOM_CLOSED') || code.includes('SESSION_CLOSED') || code.includes('NOT_ELIGIBLE');
  });
}

function deriveRuntimeState(payload: ExamTakingPayload, heartbeatDegraded: boolean): RuntimePageState {
  if (Boolean(payload.submission.sealed_at) || ['SEALED', 'SUBMITTED', 'GRADED'].includes(String(payload.submission.submission_status || '').toUpperCase())) {
    return 'sealed';
  }

  if (hasHardRuntimeBlocker(payload) || TERMINAL_SESSION_STATUSES.has(sessionStatus(payload))) {
    return 'closed_or_interrupted';
  }

  if (hasBlockedReadOnlyRuntime(payload) || hasUnsupportedRuntimeOnly(payload)) {
    return 'unsupported_runtime_mode';
  }

  if (requiresDeviceBinding(payload) && !hasActiveDeviceBinding(payload)) {
    return 'requires_device_binding';
  }

  if (ACTIVE_SESSION_STATUSES.has(sessionStatus(payload))) {
    return heartbeatDegraded ? 'heartbeat_degraded' : 'in_progress';
  }

  if (STARTABLE_SESSION_STATUSES.has(sessionStatus(payload))) {
    return 'ready_to_start';
  }

  return 'closed_or_interrupted';
}

function runtimeStateLabel(state: RuntimePageState): string {
  if (state === 'requires_device_binding') return 'Yêu cầu gắn thiết bị';
  if (state === 'ready_to_start') return 'Chưa bắt đầu';
  if (state === 'starting') return 'Đang khởi động phiên thi';
  if (state === 'in_progress') return 'Đang làm bài';
  if (state === 'heartbeat_degraded') return 'Heartbeat suy giảm';
  if (state === 'sealed') return 'Đã khóa bài';
  if (state === 'closed_or_interrupted') return 'Phiên thi bị chặn';
  if (state === 'unsupported_runtime_mode') return 'Chế độ bị chặn';
  if (state === 'runtime_error') return 'Lỗi tải phiên thi';
  return 'Đang tải';
}

function runtimeStateDescription(state: RuntimePageState): string {
  if (state === 'requires_device_binding') return 'Thiết bị phải được gắn đúng trạm trước khi có thể bắt đầu.';
  if (state === 'ready_to_start') return 'Phiên thi đã sẵn sàng nhưng chỉ bắt đầu khi bạn chủ động xác nhận.';
  if (state === 'starting') return 'Hệ thống đang yêu cầu backend chuyển phiên thi sang trạng thái làm bài.';
  if (state === 'in_progress') return 'Phiên thi đang hoạt động. Autosave văn bản và tải tệp chỉ khả dụng khi còn đủ điều kiện.';
  if (state === 'heartbeat_degraded') return 'Heartbeat tới backend bị gián đoạn. Không có trạng thái lưu hay nộp giả được hiển thị.';
  if (state === 'sealed') return 'Bài làm đã được khóa và chỉ còn ở trạng thái đọc.';
  if (state === 'closed_or_interrupted') return 'Phiên thi đã đóng, bị chặn hoặc không còn hợp lệ để tiếp tục làm bài.';
  if (state === 'unsupported_runtime_mode') return 'Backend đang cung cấp một chế độ làm bài chỉ đọc hoặc chưa sẵn sàng cho giao diện hiện tại.';
  if (state === 'runtime_error') return 'Không tải được dữ liệu runtime.';
  return 'Đang tải dữ liệu runtime từ backend.';
}

function runtimeStateTone(state: RuntimePageState): 'ok' | 'warning' | 'danger' | 'neutral' {
  if (state === 'in_progress' || state === 'sealed') return 'ok';
  if (state === 'heartbeat_degraded' || state === 'ready_to_start' || state === 'starting') return 'warning';
  if (state === 'requires_device_binding' || state === 'closed_or_interrupted' || state === 'unsupported_runtime_mode' || state === 'runtime_error') return 'danger';
  return 'neutral';
}

function bindingStationLabel(payload: ExamTakingPayload): string {
  const stationCode = payload.device_binding_requirement?.station_code || payload.device_binding?.station_code;
  const stationId = payload.device_binding_requirement?.station_id || payload.device_binding?.station_id;
  if (stationCode) return stationCode;
  if (stationId) return `Trạm ${stationId}`;
  return 'Chưa có thông tin trạm';
}

function bindingDeviceLabel(payload: ExamTakingPayload): string {
  const deviceCode = payload.device_binding?.device_code;
  const assetTag = payload.device_binding_requirement?.asset_tag || payload.device_binding?.asset_tag;
  const deviceId = payload.device_binding_requirement?.device_id || payload.device_binding?.device_id;
  if (deviceCode) return deviceCode;
  if (assetTag) return assetTag;
  if (deviceId) return `Thiết bị ${deviceId}`;
  return 'Backend chưa cung cấp mã thiết bị';
}

function questionReference(questionMap: Map<number, ExamQuestion>, questionId?: number | null): string | null {
  if (!questionId) return null;
  const question = questionMap.get(questionId);
  if (!question) return null;
  return `Câu ${question.question_order}`;
}

function buildQuestionUiModels(
  questions: ExamQuestion[],
  answers: AnswerState,
  dirtyQuestionIds: Set<number>,
  fileAnswers: FileAnswerState
): QuestionUiModel[] {
  return questions.map((question) => {
    const questionId = question.generated_exam_question_id;
    const mode = renderMode(question);
    const currentText = answers[questionId] ?? '';
    const currentFile = fileAnswers[questionId]?.currentFile ?? null;
    const isRequired = questionRequired(question);
    const isDirty = dirtyQuestionIds.has(questionId);
    const hasUploadedFile = Boolean(currentFile);
    const isAnswered = mode === 'FILE_UPLOAD' ? hasUploadedFile : currentText.trim().length > 0 || hasUploadedFile;

    let navigatorTone: QuestionNavigatorTone = 'empty';
    let navigatorLabel = 'Chưa trả lời';

    if (mode === 'UNSUPPORTED') {
      navigatorTone = 'unsupported';
      navigatorLabel = 'Không hỗ trợ';
    } else if (mode === 'INSTRUCTION_ONLY') {
      navigatorTone = 'blocked';
      navigatorLabel = 'Chỉ đọc';
    } else if (isDirty) {
      navigatorTone = 'dirty';
      navigatorLabel = 'Chưa lưu';
    } else if (mode === 'FILE_UPLOAD' && hasUploadedFile) {
      navigatorTone = 'file';
      navigatorLabel = 'Đã tải tệp';
    } else if (isAnswered) {
      navigatorTone = 'answered';
      navigatorLabel = 'Đã trả lời';
    } else if (isRequired) {
      navigatorTone = 'missing';
      navigatorLabel = 'Thiếu bắt buộc';
    }

    return {
      question,
      mode,
      answerType: answerTypeForQuestion(question),
      answerLabel: answerLabelForQuestion(question),
      helperText: answerHelperForQuestion(question),
      isRequired,
      isAnswered,
      isDirty,
      hasUploadedFile,
      navigatorTone,
      navigatorLabel,
    };
  });
}

function normalizePreflightResult(
  preflight: SealPreflightResponse,
  unsupportedQuestions: QuestionUiModel[],
  missingRequiredFileQuestions: QuestionUiModel[]
): SealPreflightResponse {
  const extraBlockers = [
    ...unsupportedQuestions.map((item) => ({
      code: 'UNSUPPORTED_QUESTION_MODE',
      message: `Giao diện hiện tại chưa thể nộp an toàn vì ${questionReference(
        new Map([[item.question.generated_exam_question_id, item.question]]),
        item.question.generated_exam_question_id
      )?.toLowerCase() || 'một câu hỏi'} đang ở chế độ không hỗ trợ.`,
      severity: 'blocker',
      generated_exam_question_id: item.question.generated_exam_question_id,
    })),
    ...missingRequiredFileQuestions.map((item) => ({
      code: 'REQUIRED_FILE_MISSING_LOCAL',
      message: `${questionReference(new Map([[item.question.generated_exam_question_id, item.question]]), item.question.generated_exam_question_id) || 'Một câu hỏi'} chưa có tệp bài làm bắt buộc.`,
      severity: 'blocker',
      generated_exam_question_id: item.question.generated_exam_question_id,
    })),
  ];

  return {
    ...preflight,
    can_seal: preflight.can_seal && extraBlockers.length === 0,
    blockers: [...preflight.blockers, ...extraBlockers],
  };
}

function ExamRuntimeHeader({
  payload,
  runtimeState,
  answeredCount,
  totalQuestions,
  remainingSeconds,
  isOnline,
  autosaveStatus,
  autosaveError,
  heartbeatError,
  onSaveNow,
  saveDisabled,
}: {
  payload: ExamTakingPayload;
  runtimeState: RuntimePageState;
  answeredCount: number;
  totalQuestions: number;
  remainingSeconds: number | null;
  isOnline: boolean;
  autosaveStatus: AutosaveStatus;
  autosaveError: string | null;
  heartbeatError: string | null;
  onSaveNow: () => void;
  saveDisabled: boolean;
}) {
  const deadline = formatDateTime(payload.timer?.deadline_at || payload.session.deadline_at);
  const startedAt = formatDateTime(payload.session.started_at);
  const roomLabel = payload.session.room_name || payload.session.room_code || 'Chưa có thông tin phòng';
  const stationLabel = payload.session.station_code || bindingStationLabel(payload);

  return (
    <header className="exam-runtime-header" aria-labelledby="exam-taking-title">
      <div className="exam-runtime-header-main">
        <div className="exam-runtime-title-block">
          <nav className="exam-breadcrumb" aria-label="Điều hướng bài thi">
            <Link to="/dashboard">Dashboard</Link>
            <span aria-hidden="true">/</span>
            <Link to="/exams">Danh sách ca thi</Link>
            <span aria-hidden="true">/</span>
            <span aria-current="page">Ca hiện tại</span>
          </nav>
          <p className="eyebrow">Màn hình làm bài</p>
          <h2 id="exam-taking-title">{examTitle(payload)}</h2>
          <p className="exam-runtime-subtitle">
            {payload.session.session_code ? `Mã ca thi ${payload.session.session_code}` : `Ca thi #${payload.session.exam_session_id}`}
          </p>
          <div className="exam-runtime-chip-row" aria-label="Trạng thái runtime">
            <span className={`runtime-chip runtime-chip-${runtimeStateTone(runtimeState)}`}>{runtimeStateLabel(runtimeState)}</span>
            <span className={`runtime-chip ${isOnline ? 'runtime-chip-ok' : 'runtime-chip-danger'}`}>
              {isOnline ? 'Đang kết nối' : 'Mất kết nối'}
            </span>
            <span className="runtime-chip runtime-chip-neutral">{submissionStatusText(payload.submission.submission_status)}</span>
          </div>
        </div>
        <ExamTakerIdentityPanel candidate={payload.candidate} compact />
      </div>

      <dl className="exam-runtime-overview" aria-label="Thông tin phiên thi">
        <div>
          <dt>Trạng thái phiên</dt>
          <dd>{sessionStatusText(payload.session.session_status)}</dd>
        </div>
        <div>
          <dt>Phòng thi</dt>
          <dd>{roomLabel}</dd>
        </div>
        <div>
          <dt>Trạm thi</dt>
          <dd>{stationLabel}</dd>
        </div>
        <div>
          <dt>Bắt đầu</dt>
          <dd>{startedAt || 'Chưa bắt đầu'}</dd>
        </div>
      </dl>

      <div className="exam-header-metrics" aria-label="Thông tin tiến độ bài thi">
        <div className="metric-card">
          <span>Tiến độ</span>
          <strong>
            {answeredCount}/{totalQuestions} câu
          </strong>
        </div>
        <div className="metric-card timer-box">
          <span>Thời gian còn lại</span>
          <strong>{formatRemaining(remainingSeconds ?? payload.timer?.remaining_seconds ?? payload.session.remaining_seconds)}</strong>
          <small>{deadline ? `Hạn cuối ${deadline}` : 'Backend chưa cung cấp deadline'}</small>
        </div>
        <div className={`metric-card autosave-card autosave-${autosaveStatus}`} aria-live="polite">
          <span>Autosave văn bản</span>
          <strong>{statusText(autosaveStatus)}</strong>
          <small>{autosaveError || statusDetail(autosaveStatus, isOnline)}</small>
          <button
            type="button"
            className="secondary-button compact-button"
            onClick={onSaveNow}
            disabled={saveDisabled}
          >
            Lưu ngay
          </button>
        </div>
        <div className={`metric-card ${runtimeState === 'heartbeat_degraded' ? 'heartbeat-card-degraded' : 'heartbeat-card-active'}`}>
          <span>Heartbeat</span>
          <strong>{runtimeState === 'heartbeat_degraded' ? 'Suy giảm' : runtimeState === 'in_progress' ? 'Đang hoạt động' : 'Chưa hoạt động'}</strong>
          <small>{heartbeatError || runtimeStateDescription(runtimeState)}</small>
        </div>
      </div>
    </header>
  );
}

function RuntimeStatusBanner({
  runtimeState,
  autosaveError,
  heartbeatError,
  isOnline,
}: {
  runtimeState: RuntimePageState;
  autosaveError: string | null;
  heartbeatError: string | null;
  isOnline: boolean;
}) {
  if (runtimeState === 'heartbeat_degraded') {
    return (
      <section className="runtime-status-banner is-warning" role="status" aria-live="polite">
        <strong>Heartbeat tới backend đang bị gián đoạn.</strong>
        <p>{heartbeatError || 'Phiên thi không được đánh dấu là đã nộp hoặc đã lưu khi heartbeat chưa được máy chủ xác nhận.'}</p>
      </section>
    );
  }

  if (!isOnline) {
    return (
      <section className="runtime-status-banner is-warning" role="status" aria-live="polite">
        <strong>Thiết bị đang offline.</strong>
        <p>Câu trả lời hiện vẫn ở trên màn hình nhưng chưa có xác nhận đã lưu từ backend.</p>
      </section>
    );
  }

  if (autosaveError) {
    return (
      <section className="runtime-status-banner is-danger" role="alert">
        <strong>Autosave chưa thành công.</strong>
        <p>{autosaveError}</p>
      </section>
    );
  }

  return null;
}

function RuntimeGateLayout({
  payload,
  runtimeState,
  children,
  answeredCount,
  totalQuestions,
  remainingSeconds,
  isOnline,
}: {
  payload: ExamTakingPayload;
  runtimeState: RuntimePageState;
  children: React.ReactNode;
  answeredCount: number;
  totalQuestions: number;
  remainingSeconds: number | null;
  isOnline: boolean;
}) {
  return (
    <section className="exam-taking-page student-exam-workspace">
      <ExamRuntimeHeader
        payload={payload}
        runtimeState={runtimeState}
        answeredCount={answeredCount}
        totalQuestions={totalQuestions}
        remainingSeconds={remainingSeconds}
        isOnline={isOnline}
        autosaveStatus="idle"
        autosaveError={null}
        heartbeatError={null}
        onSaveNow={() => undefined}
        saveDisabled
      />
      <div className="runtime-single-panel">{children}</div>
    </section>
  );
}

function DeviceBindingGate({
  payload,
  bindingBusy,
  bindingError,
  onBind,
}: {
  payload: ExamTakingPayload;
  bindingBusy: boolean;
  bindingError: string | null;
  onBind: () => void;
}) {
  const canBind = Boolean(payload.device_binding_requirement?.station_id ?? payload.device_binding?.station_id);

  return (
    <section className="card runtime-gate-card" aria-live="polite">
      <h3>Yêu cầu gắn thiết bị</h3>
      <p className="muted">
        Phiên thi này phải xác nhận đúng trạm và thiết bị trước khi backend cho phép bắt đầu. Autosave, tải tệp và heartbeat chỉ hoạt động sau khi phiên thi được bắt đầu hợp lệ.
      </p>
      <dl className="runtime-gate-details">
        <div>
          <dt>Trạm được chỉ định</dt>
          <dd>{bindingStationLabel(payload)}</dd>
        </div>
        <div>
          <dt>Thiết bị</dt>
          <dd>{bindingDeviceLabel(payload)}</dd>
        </div>
        <div>
          <dt>Lý do gắn</dt>
          <dd>{payload.device_binding_requirement?.bind_reason || 'INITIAL_START'}</dd>
        </div>
      </dl>
      {bindingError ? (
        <p className="form-error" role="alert">
          {bindingError}
        </p>
      ) : null}
      <div className="runtime-gate-actions">
        <button type="button" className="primary-button" onClick={onBind} disabled={bindingBusy || !canBind}>
          {bindingBusy ? 'Đang gắn thiết bị...' : canBind ? 'Xác nhận thiết bị' : 'Không thể gắn thiết bị'}
        </button>
        <Link className="secondary-link" to="/exams">
          Quay lại danh sách ca thi
        </Link>
      </div>
    </section>
  );
}

function StartExamGate({
  payload,
  runtimeState,
  onStart,
}: {
  payload: ExamTakingPayload;
  runtimeState: RuntimePageState;
  onStart: () => void;
}) {
  return (
    <section className="card runtime-gate-card" aria-live="polite">
      <h3>Sẵn sàng bắt đầu</h3>
      <p className="muted">
        Phiên thi đã được backend cho phép mở. Bài thi sẽ không tự khởi động: bạn phải chủ động bấm bắt đầu. Autosave, tải tệp và heartbeat chỉ bắt đầu sau khi trạng thái in-progress được backend xác nhận.
      </p>
      <dl className="runtime-gate-details">
        <div>
          <dt>Trạng thái phiên</dt>
          <dd>{sessionStatusText(payload.session.session_status)}</dd>
        </div>
        <div>
          <dt>Trạng thái bài làm</dt>
          <dd>{submissionStatusText(payload.submission.submission_status)}</dd>
        </div>
      </dl>
      <div className="runtime-gate-actions">
        <button type="button" className="primary-button" onClick={onStart} disabled={runtimeState === 'starting'}>
          {runtimeState === 'starting' ? 'Đang bắt đầu...' : 'Bắt đầu làm bài'}
        </button>
      </div>
    </section>
  );
}

function SubmissionSealedPanel({ submissionId }: { submissionId: number }) {
  return (
    <section className="card runtime-gate-card" aria-live="polite">
      <h3>Bài làm đã được khóa</h3>
      <p className="muted">
        Phiên thi đã ở trạng thái chỉ đọc. Bạn không thể chỉnh sửa câu trả lời, tải lại tệp hoặc gửi heartbeat như một phiên đang làm bài.
      </p>
      <div className="runtime-gate-actions">
        <Link className="primary-button action-link" to={`/submissions/${submissionId}/result`}>
          Xem trạng thái xử lý
        </Link>
      </div>
    </section>
  );
}

function UnsupportedRuntimePanel({
  payload,
  title,
  summary,
}: {
  payload: ExamTakingPayload;
  title: string;
  summary: string;
}) {
  const readiness = payload.runtime_contract?.runtime_readiness || payload.delivery_profile?.runtime_readiness || 'UNKNOWN';
  const modality = payload.runtime_contract?.modality || payload.delivery_profile?.modality || 'UNKNOWN';

  return (
    <section className="card runtime-gate-card" aria-live="polite">
      <h3>{title}</h3>
      <p className="muted">{summary}</p>
      <dl className="runtime-gate-details">
        <div>
          <dt>Runtime readiness</dt>
          <dd>{String(readiness)}</dd>
        </div>
        <div>
          <dt>Modality</dt>
          <dd>{String(modality)}</dd>
        </div>
      </dl>
      {(payload.blockers || []).length > 0 ? (
        <section className="runtime-blocker-panel">
          <h4>Backend blockers</h4>
          <ul>
            {(payload.blockers || []).map((blocker) => (
              <li key={`${blocker.code}-${blocker.generated_exam_question_id || 'runtime'}`}>
                <strong>{blocker.code}</strong>: {blocker.message}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <div className="runtime-gate-actions">
        <Link className="secondary-link" to="/exams">
          Quay lại danh sách ca thi
        </Link>
      </div>
    </section>
  );
}

function QuestionNavigator({
  questions,
  currentQuestionId,
  onSelectQuestion,
}: {
  questions: QuestionUiModel[];
  currentQuestionId: number | null;
  onSelectQuestion: (questionId: number) => void;
}) {
  return (
    <section className="side-panel-section" aria-label="Điều hướng câu hỏi">
      <div className="section-heading">
        <div>
          <h3>Câu hỏi</h3>
          <p className="muted">Mỗi trạng thái phản ánh backend hoặc dữ liệu hiện trên màn hình, không có trạng thái nộp giả.</p>
        </div>
      </div>
      <nav className="question-nav-list" aria-label="Danh sách câu hỏi">
        {questions.map((item) => {
          const questionId = item.question.generated_exam_question_id;
          const isCurrent = currentQuestionId === questionId;
          return (
            <button
              key={questionId}
              type="button"
              className={`question-nav-item question-nav-${item.navigatorTone}${isCurrent ? ' is-current' : ''}`}
              aria-current={isCurrent ? 'true' : undefined}
              onClick={() => onSelectQuestion(questionId)}
            >
              <span className="question-nav-order">Câu {item.question.question_order}</span>
              <strong>{item.question.question_code || `Q${item.question.question_order}`}</strong>
              <small>{item.navigatorLabel}</small>
            </button>
          );
        })}
      </nav>
    </section>
  );
}

function TextAnswerEditor({
  question,
  answerLabel,
  helperText,
  value,
  readOnly,
  rows,
  onChange,
  onFocus,
}: {
  question: ExamQuestion;
  answerLabel: string;
  helperText: string | null;
  value: string;
  readOnly: boolean;
  rows: number;
  onChange: (event: ChangeEvent<HTMLTextAreaElement>) => void;
  onFocus: () => void;
}) {
  const helperId = helperText ? `question-${question.generated_exam_question_id}-helper` : undefined;

  return (
    <label className="answer-field">
      <span>{answerLabel}</span>
      {helperText ? (
        <small id={helperId} className="answer-field-helper">
          {helperText}
        </small>
      ) : null}
      <textarea
        value={value}
        onChange={onChange}
        onFocus={onFocus}
        rows={rows}
        spellCheck={false}
        readOnly={readOnly}
        aria-describedby={helperId}
      />
    </label>
  );
}

function FileAnswerUploader({
  item,
  state,
  disabled,
  onChooseFile,
  onUpload,
  onFocus,
}: {
  item: QuestionUiModel;
  state: FileState | undefined;
  disabled: boolean;
  onChooseFile: (event: ChangeEvent<HTMLInputElement>) => void;
  onUpload: () => void;
  onFocus: () => void;
}) {
  const currentFile = state?.currentFile;

  return (
    <section className="answer-file-block" aria-label={`Đính kèm bài làm câu ${item.question.question_order}`}>
      <div className="answer-file-header">
        <h4>Đính kèm bài làm</h4>
        <span className={`runtime-chip ${currentFile ? 'runtime-chip-ok' : 'runtime-chip-neutral'}`}>
          {currentFile ? 'Đã có tệp backend' : 'Chưa có tệp'}
        </span>
      </div>

      <label className="answer-file-field">
        <span>Chọn tệp</span>
        <input
          type="file"
          accept={(item.question.answer_ui?.allowed_extensions || []).join(',') || undefined}
          onChange={onChooseFile}
          onFocus={onFocus}
          disabled={disabled || state?.uploading}
        />
      </label>

      <dl className="answer-file-policy">
        <div>
          <dt>Đuôi tệp cho phép</dt>
          <dd>{joinAllowedValues(item.question.answer_ui?.allowed_extensions)}</dd>
        </div>
        <div>
          <dt>MIME cho phép</dt>
          <dd>{joinAllowedValues(item.question.answer_ui?.allowed_mime_types)}</dd>
        </div>
        <div>
          <dt>Kích thước tối đa</dt>
          <dd>{item.question.answer_ui?.max_file_size_bytes ? formatBytes(Number(item.question.answer_ui.max_file_size_bytes)) : '--'}</dd>
        </div>
      </dl>

      {state?.selectedFile ? (
        <p className="answer-file-selected">
          Tệp đã chọn: <strong>{state.selectedFile.name}</strong> ({formatBytes(state.selectedFile.size)})
        </p>
      ) : null}

      <div className="answer-file-meta" aria-live="polite">
        <strong>Tệp đã tải lên</strong>
        {currentFile ? (
          <ul>
            <li>{currentFile.original_filename}</li>
            <li>{formatBytes(currentFile.file_size_bytes)}</li>
            <li>{currentFile.mime_type || 'Không có MIME'}</li>
            <li>sha256: {shortHash(currentFile.sha256_hash)}</li>
            <li>{currentFile.status || 'Không có trạng thái backend'}</li>
          </ul>
        ) : (
          <p className="muted">Chưa có metadata tệp từ backend.</p>
        )}
      </div>

      <div className="answer-file-actions">
        <button
          type="button"
          className="secondary-button"
          disabled={disabled || state?.uploading || !state?.selectedFile}
          onClick={onUpload}
        >
          {state?.uploading ? 'Đang tải tệp...' : currentFile ? 'Thay tệp' : 'Tải tệp'}
        </button>
      </div>

      {state?.error ? (
        <p className="form-error" role="alert">
          {state.error || 'Không thể tải tệp bài làm.'}
        </p>
      ) : null}
    </section>
  );
}

function SealPreflightPanel({
  phase,
  preflight,
  questionMap,
  onConfirmSeal,
  onDismiss,
}: {
  phase: SubmitPhase;
  preflight: SealPreflightResponse | null;
  questionMap: Map<number, ExamQuestion>;
  onConfirmSeal: () => void;
  onDismiss: () => void;
}) {
  if (phase === 'idle' || !preflight) return null;

  if (phase === 'checking_preflight') {
    return (
      <section className="seal-preflight-panel" aria-live="polite">
        <h3>Đang kiểm tra trước khi nộp</h3>
        <p className="muted">Backend đang xác minh điều kiện seal trước khi cho phép khóa bài.</p>
      </section>
    );
  }

  const blockers = preflight.blockers || [];
  const warnings = preflight.warnings || [];
  const isConfirm = phase === 'ready_to_seal' || phase === 'sealing';

  return (
    <section className={`seal-preflight-panel${isConfirm ? ' is-confirm' : ' is-blocked'}`} aria-live="polite">
      <div className="seal-preflight-header">
        <div>
          <h3>{isConfirm ? 'Sẵn sàng nộp và khóa bài' : 'Preflight đang chặn nộp bài'}</h3>
          <p className="muted">
            {isConfirm
              ? 'Backend đã cho phép seal. Hãy xác nhận lần cuối trước khi khóa bài.'
              : 'Seal chưa được phép. Các blocker dưới đây phải được xử lý trước khi có thể nộp.'}
          </p>
        </div>
        <span className={`runtime-chip ${isConfirm ? 'runtime-chip-ok' : 'runtime-chip-danger'}`}>
          {isConfirm ? 'can_seal = true' : 'can_seal = false'}
        </span>
      </div>

      {blockers.length > 0 ? (
        <div className="preflight-list-block">
          <h4>Blockers</h4>
          <ul>
            {blockers.map((blocker) => (
              <li key={`${blocker.code}-${blocker.generated_exam_question_id || 'runtime'}`}>
                <strong>{questionReference(questionMap, blocker.generated_exam_question_id) || blocker.code}</strong>
                <span>{blocker.message}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {warnings.length > 0 ? (
        <div className="preflight-list-block">
          <h4>Warnings</h4>
          <ul>
            {warnings.map((warning) => (
              <li key={`${warning.code}-${warning.generated_exam_question_id || 'runtime'}`}>
                <strong>{questionReference(questionMap, warning.generated_exam_question_id) || warning.code}</strong>
                <span>{warning.message}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="seal-preflight-actions">
        {isConfirm ? (
          <button type="button" className="primary-button" onClick={onConfirmSeal} disabled={phase === 'sealing'}>
            {phase === 'sealing' ? 'Đang nộp bài...' : 'Xác nhận nộp và khóa bài'}
          </button>
        ) : null}
        <button type="button" className="secondary-button" onClick={onDismiss} disabled={phase === 'sealing'}>
          Đóng panel
        </button>
      </div>
    </section>
  );
}

export function ExamTakingPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const autosaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sequenceRef = useRef(0);

  const [payload, setPayload] = useState<ExamTakingPayload | null>(null);
  const [answers, setAnswers] = useState<AnswerState>({});
  const [revisions, setRevisions] = useState<RevisionState>({});
  const [dirtyQuestionIds, setDirtyQuestionIds] = useState<Set<number>>(new Set());
  const [fileAnswers, setFileAnswers] = useState<FileAnswerState>({});
  const [autosaveStatus, setAutosaveStatus] = useState<AutosaveStatus>('idle');
  const [autosaveError, setAutosaveError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitPhase, setSubmitPhase] = useState<SubmitPhase>('idle');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [preflightResult, setPreflightResult] = useState<SealPreflightResponse | null>(null);
  const [paperAssets, setPaperAssets] = useState<ExamSessionPaperAsset[]>([]);
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);
  const [isOnline, setIsOnline] = useState(typeof navigator !== 'undefined' ? navigator.onLine : true);
  const [runtimeState, setRuntimeState] = useState<RuntimePageState>('loading_runtime');
  const [bindingError, setBindingError] = useState<string | null>(null);
  const [bindingBusy, setBindingBusy] = useState(false);
  const [heartbeatError, setHeartbeatError] = useState<string | null>(null);
  const [currentQuestionId, setCurrentQuestionId] = useState<number | null>(null);

  useEffect(() => {
    function handleOnline() {
      setIsOnline(true);
    }
    function handleOffline() {
      setIsOnline(false);
    }
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const resetSubmissionUi = useCallback(() => {
    setSubmitError(null);
    setSubmitPhase('idle');
    setPreflightResult(null);
  }, []);

  function resolveRemainingSeconds(payloadData: ExamTakingPayload): number | null {
    const deadline = payloadData.timer?.deadline_at || payloadData.session.deadline_at;
    if (deadline) {
      const deadlineMs = new Date(deadline).getTime();
      if (Number.isFinite(deadlineMs)) {
        return Math.max(0, Math.floor((deadlineMs - Date.now()) / 1000));
      }
    }
    const value = payloadData.timer?.remaining_seconds ?? payloadData.session.remaining_seconds;
    return value == null ? null : Math.max(0, Math.floor(Number(value)));
  }

  const loadExam = useCallback(async () => {
    if (!id || !/^\d+$/.test(id)) {
      setLoadError('Mã ca thi không hợp lệ.');
      setRuntimeState('runtime_error');
      setLoading(false);
      return null;
    }

    setLoading(true);
    setRuntimeState('loading_runtime');
    setLoadError(null);
    setBindingError(null);

    try {
      const payloadData = await getExamRuntimePayload(id);
      const nextAnswers: AnswerState = {};
      const nextRevisions: RevisionState = {};
      const knownQuestionIds = new Set(payloadData.paper.questions.map((question) => question.generated_exam_question_id));
      const nextFileAnswers = initialFileAnswerState(payloadData.paper.questions);

      const paperAssetResponse = await loadExamSessionPaperAssets(payloadData.session.exam_session_id);
      if (paperAssetResponse.ok) {
        setPaperAssets(Array.isArray(paperAssetResponse.data.items) ? paperAssetResponse.data.items : []);
      } else {
        setPaperAssets([]);
      }

      const answerStateResponse = await loadAnswerState(payloadData.submission.exam_submission_id);
      if (answerStateResponse.ok) {
        answerStateResponse.data.items.forEach((item) => {
          const questionId = Number(item.generated_exam_question_id);
          if (!knownQuestionIds.has(questionId)) return;
          if (typeof item.answer_text === 'string') {
            nextAnswers[questionId] = item.answer_text;
          }
          const revision = Number(item.server_version ?? item.client_version ?? 1);
          nextRevisions[questionId] = Number.isFinite(revision) && revision > 0 ? revision : 1;
        });
      }

      setPayload(payloadData);
      setRemainingSeconds(resolveRemainingSeconds(payloadData));
      setAnswers(nextAnswers);
      setRevisions(nextRevisions);
      setFileAnswers(nextFileAnswers);
      setDirtyQuestionIds(new Set());
      setAutosaveStatus('idle');
      setAutosaveError(null);
      setHeartbeatError(null);
      resetSubmissionUi();
      setCurrentQuestionId(payloadData.paper.questions[0]?.generated_exam_question_id ?? null);
      setRuntimeState(deriveRuntimeState(payloadData, false));
      setLoading(false);
      return payloadData;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Không tải được dữ liệu bài thi.';
      const code = typeof error === 'object' && error !== null && 'code' in error ? String((error as { code?: string }).code) : undefined;
      setLoadError(userSafeError(code, message));
      setRuntimeState('runtime_error');
      setLoading(false);
      return null;
    }
  }, [id, resetSubmissionUi]);

  useEffect(() => {
    void loadExam();
    return () => {
      if (autosaveTimerRef.current) clearTimeout(autosaveTimerRef.current);
      if (heartbeatTimerRef.current) window.clearInterval(heartbeatTimerRef.current);
    };
  }, [loadExam]);

  const questionItems = useMemo(
    () => (payload ? buildQuestionUiModels(payload.paper.questions, answers, dirtyQuestionIds, fileAnswers) : []),
    [answers, dirtyQuestionIds, fileAnswers, payload]
  );

  useEffect(() => {
    if (questionItems.length === 0) {
      setCurrentQuestionId(null);
      return;
    }
    if (!questionItems.some((item) => item.question.generated_exam_question_id === currentQuestionId)) {
      setCurrentQuestionId(questionItems[0].question.generated_exam_question_id);
    }
  }, [currentQuestionId, questionItems]);

  const fileUploadQuestions = useMemo(() => questionItems.filter((item) => item.mode === 'FILE_UPLOAD'), [questionItems]);
  const unsupportedQuestions = useMemo(() => questionItems.filter((item) => item.mode === 'UNSUPPORTED'), [questionItems]);
  const missingRequiredFileQuestions = useMemo(
    () => questionItems.filter((item) => item.mode === 'FILE_UPLOAD' && item.isRequired && !item.hasUploadedFile),
    [questionItems]
  );

  const dirtyAnswers = useMemo(() => {
    return questionItems
      .filter((item) => item.mode === 'TEXT' && item.isDirty)
      .map((item): AutosaveAnswerDraft => ({
        generated_exam_question_id: item.question.generated_exam_question_id,
        answer_type: item.answerType,
        answer_text: answers[item.question.generated_exam_question_id] ?? '',
        client_revision: revisions[item.question.generated_exam_question_id] ?? 1,
      }));
  }, [answers, questionItems, revisions]);

  const answeredQuestionIds = useMemo(() => {
    const next = new Set<number>();
    questionItems.forEach((item) => {
      if (item.isAnswered) {
        next.add(item.question.generated_exam_question_id);
      }
    });
    return next;
  }, [questionItems]);

  const isSealed = useMemo(() => {
    if (!payload) return false;
    const status = String(payload.submission.submission_status || '').toUpperCase();
    return Boolean(payload.submission.sealed_at || ['SEALED', 'SUBMITTED', 'GRADED'].includes(status));
  }, [payload]);

  const isWorkspaceInteractive = runtimeState === 'in_progress' || runtimeState === 'heartbeat_degraded';
  const hasPendingUploads = fileUploadQuestions.some((item) => fileAnswers[item.question.generated_exam_question_id]?.uploading);

  useEffect(() => {
    const hasCountdown = remainingSeconds != null;
    if (!payload || !hasCountdown || isSealed) return;
    const intervalId = window.setInterval(() => {
      setRemainingSeconds((current) => {
        if (current == null) return current;
        return Math.max(0, current - 1);
      });
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [isSealed, payload, remainingSeconds]);

  const activePaperAsset = useMemo(() => selectActivePaperAsset(paperAssets), [paperAssets]);
  const hasVisualPaper = Boolean(activePaperAsset?.content_url);
  const visualPaperWatermark = useMemo(() => {
    if (!payload) return '';
    return `${payload.session.session_code || ''} | session:${payload.session.exam_session_id} | submission:${payload.submission.exam_submission_id}`;
  }, [payload]);

  useEffect(() => {
    const sessionId = payload?.session.exam_session_id;
    if (!sessionId) return;

    if (heartbeatTimerRef.current) {
      window.clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }

    if (runtimeState !== 'in_progress') {
      return;
    }

    let cancelled = false;

    heartbeatTimerRef.current = window.setInterval(async () => {
      try {
        const heartbeatResponse = await sendHeartbeat(sessionId, {
          last_activity_at: new Date().toISOString(),
          metadata_json: { source: 'frontend_exam_taking_heartbeat' },
        });
        if (cancelled) return;
        setHeartbeatError(null);
        setPayload((current) =>
          current
            ? {
                ...current,
                session: {
                  ...current.session,
                  ...heartbeatResponse,
                },
                timer: heartbeatResponse.timer || current.timer,
              }
            : current
        );
        setRemainingSeconds((current) => heartbeatResponse.timer?.remaining_seconds ?? current);
      } catch (error) {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : 'Heartbeat failed';
        const code = typeof error === 'object' && error !== null && 'code' in error ? String((error as { code?: string }).code) : undefined;
        setHeartbeatError(userSafeError(code, message));
        setRuntimeState('heartbeat_degraded');
      }
    }, HEARTBEAT_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (heartbeatTimerRef.current) {
        window.clearInterval(heartbeatTimerRef.current);
        heartbeatTimerRef.current = null;
      }
    };
  }, [payload?.session.exam_session_id, runtimeState]);

  const runAutosave = useCallback(async (): Promise<boolean> => {
    if (!payload || dirtyAnswers.length === 0) return true;
    if (!isWorkspaceInteractive) return false;

    sequenceRef.current += 1;
    setAutosaveStatus('saving');
    setAutosaveError(null);

    if (!isOnline) {
      setAutosaveStatus('unsynced');
      setAutosaveError('Câu trả lời hiện chưa được lưu lên máy chủ.');
      return false;
    }

    const response = await autosaveAnswers(payload.submission.exam_submission_id, {
      answers: dirtyAnswers,
      clientRevision: Math.max(...dirtyAnswers.map((answer) => answer.client_revision), 1),
      clientSequenceNo: sequenceRef.current,
      idempotencyKey: makeClientKey(`autosave-${payload.submission.exam_submission_id}`),
    });

    if (!response.ok) {
      setAutosaveStatus('failed');
      setAutosaveError(userSafeError(response.error.code, response.error.message));
      return false;
    }

    const savedIds = new Set(dirtyAnswers.map((answer) => answer.generated_exam_question_id));
    setDirtyQuestionIds((current) => {
      const next = new Set(current);
      savedIds.forEach((questionId) => next.delete(questionId));
      return next;
    });
    setAutosaveStatus('saved');
    return true;
  }, [dirtyAnswers, isOnline, isWorkspaceInteractive, payload]);

  useEffect(() => {
    if (!payload || dirtyQuestionIds.size === 0 || !isWorkspaceInteractive) return;
    if (autosaveTimerRef.current) clearTimeout(autosaveTimerRef.current);
    autosaveTimerRef.current = setTimeout(() => {
      void runAutosave();
    }, AUTOSAVE_DEBOUNCE_MS);
    return () => {
      if (autosaveTimerRef.current) clearTimeout(autosaveTimerRef.current);
    };
  }, [dirtyQuestionIds, isWorkspaceInteractive, payload, runAutosave]);

  const questionMap = useMemo(
    () => new Map((payload?.paper.questions || []).map((question) => [question.generated_exam_question_id, question])),
    [payload]
  );

  function focusQuestion(questionId: number) {
    setCurrentQuestionId(questionId);
    const target = document.getElementById(`question-${questionId}`);
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function handleAnswerChange(question: ExamQuestion, event: ChangeEvent<HTMLTextAreaElement>) {
    const value = event.target.value;
    const questionId = question.generated_exam_question_id;
    setCurrentQuestionId(questionId);
    setAnswers((current) => ({ ...current, [questionId]: value }));
    setRevisions((current) => ({
      ...current,
      [questionId]: (current[questionId] ?? 0) + 1,
    }));
    setDirtyQuestionIds((current) => new Set(current).add(questionId));
    setAutosaveStatus('dirty');
    setAutosaveError(null);
    resetSubmissionUi();
  }

  function handleChooseFile(questionId: number, event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0] || null;
    setCurrentQuestionId(questionId);
    setFileAnswers((current) => {
      const base = current[questionId] || {
        currentFile: null,
        selectedFile: null,
        uploading: false,
        error: null,
      };
      return {
        ...current,
        [questionId]: {
          ...base,
          selectedFile,
          error: null,
        },
      };
    });
    resetSubmissionUi();
  }

  async function handleUploadFile(question: ExamQuestion) {
    if (!payload || isSealed || !isWorkspaceInteractive) return;
    const questionId = question.generated_exam_question_id;
    setCurrentQuestionId(questionId);
    const state = fileAnswers[questionId];
    if (!state?.selectedFile) {
      setFileAnswers((current) => ({
        ...current,
        [questionId]: {
          ...(current[questionId] || { currentFile: null, selectedFile: null, uploading: false }),
          error: 'Vui lòng chọn tệp.',
          uploading: false,
        },
      }));
      return;
    }

    setFileAnswers((current) => ({
      ...current,
      [questionId]: {
        ...(current[questionId] || { currentFile: null, selectedFile: null, error: null }),
        uploading: true,
        error: null,
      },
    }));

    const response = await uploadAnswerFile(payload.submission.exam_submission_id, questionId, state.selectedFile, {
      source: 'frontend_exam_taking',
    });

    if (!response.ok) {
      setFileAnswers((current) => ({
        ...current,
        [questionId]: {
          ...(current[questionId] || { currentFile: null, selectedFile: null, error: null }),
          uploading: false,
          error: userSafeError(response.error.code, response.error.message) || 'Không thể tải tệp bài làm.',
        },
      }));
      return;
    }

    const uploaded = response.data.answer_file;
    const serverFile: QuestionFileMetadata = {
      file_asset_id: Number(uploaded.file_asset_id),
      original_filename: uploaded.file_name,
      mime_type: uploaded.mime_type,
      file_size_bytes: Number(uploaded.file_size_bytes),
      sha256_hash: uploaded.sha256,
      uploaded_at: uploaded.uploaded_at || null,
      status: uploaded.status || null,
    };
    setFileAnswers((current) => applyServerFile(current, questionId, serverFile, true));
    resetSubmissionUi();
  }

  async function handleBindDevice() {
    if (!payload || bindingBusy) return;
    const stationId = payload.device_binding_requirement?.station_id ?? payload.device_binding?.station_id;
    if (!stationId) {
      setBindingError('Không thể gắn thiết bị trên giao diện hiện tại vì chưa có thông tin trạm thi.');
      return;
    }

    setBindingBusy(true);
    setBindingError(null);
    try {
      await bindExamDevice(payload.session.exam_session_id, {
        station_id: stationId,
        device_id: payload.device_binding_requirement?.device_id ?? payload.device_binding?.device_id ?? undefined,
        bind_reason: payload.device_binding_requirement?.bind_reason ?? 'INITIAL_START',
        hostname: typeof window !== 'undefined' ? window.location.hostname : undefined,
        metadata_json: { source: 'frontend_exam_taking' },
      });
      await loadExam();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Không thể gắn thiết bị.';
      const code = typeof error === 'object' && error !== null && 'code' in error ? String((error as { code?: string }).code) : undefined;
      setBindingError(userSafeError(code, message));
    } finally {
      setBindingBusy(false);
    }
  }

  async function handleStartExam() {
    if (!payload || runtimeState !== 'ready_to_start') return;
    setRuntimeState('starting');
    setLoadError(null);
    setHeartbeatError(null);
    try {
      const response = await startExamSessionStrict(payload.session.exam_session_id, {
        metadata_json: { source: 'frontend_exam_taking' },
      });
      const nextPayload: ExamTakingPayload = {
        ...payload,
        session: {
          ...payload.session,
          ...response,
        },
        timer: response.timer || payload.timer,
      };
      setPayload(nextPayload);
      setRemainingSeconds(resolveRemainingSeconds(nextPayload));
      setRuntimeState('in_progress');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Không thể bắt đầu bài thi.';
      const code = typeof error === 'object' && error !== null && 'code' in error ? String((error as { code?: string }).code) : undefined;
      setLoadError(userSafeError(code, message));
      setRuntimeState('runtime_error');
    }
  }

  async function handleSubmit() {
    if (!payload || submitPhase === 'checking_preflight' || submitPhase === 'sealing') return;

    if (isSealed) {
      navigate(`/submissions/${payload.submission.exam_submission_id}/result`);
      return;
    }

    if (!isWorkspaceInteractive) {
      setSubmitError('Bài thi chưa ở trạng thái cho phép nộp bài.');
      return;
    }

    if (hasPendingUploads) {
      setSubmitError('Vui lòng chờ tải tệp hoàn tất trước khi nộp bài.');
      return;
    }

    setSubmitPhase('checking_preflight');
    setSubmitError(null);
    if (autosaveTimerRef.current) clearTimeout(autosaveTimerRef.current);

    const saved = await runAutosave();
    if (!saved) {
      setSubmitError('Chưa thể nộp bài vì autosave đang lỗi. Câu trả lời trên màn hình vẫn được giữ nguyên.');
      setSubmitPhase('idle');
      return;
    }

    try {
      const preflight = await getSealPreflight(payload.submission.exam_submission_id);
      const normalized = normalizePreflightResult(preflight, unsupportedQuestions, missingRequiredFileQuestions);
      setPreflightResult(normalized);

      if (!normalized.can_seal || normalized.blockers.length > 0) {
        setSubmitPhase('blocked');
        return;
      }

      setSubmitPhase('ready_to_seal');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Không thể kiểm tra điều kiện nộp bài.';
      const code = typeof error === 'object' && error !== null && 'code' in error ? String((error as { code?: string }).code) : undefined;
      setSubmitError(userSafeError(code, message));
      setSubmitPhase('idle');
    }
  }

  async function handleConfirmSeal() {
    if (!payload || !preflightResult || submitPhase === 'sealing') return;

    setSubmitPhase('sealing');
    const response = await sealSubmission(payload.submission.exam_submission_id, makeClientKey(`seal-${payload.submission.exam_submission_id}`));
    if (!response.ok) {
      setSubmitError(userSafeError(response.error.code, response.error.message));
      setSubmitPhase('ready_to_seal');
      return;
    }

    setRuntimeState('sealed');
    const examSubmissionId = response.data.exam_submission_id || payload.submission.exam_submission_id;
    navigate(`/submissions/${examSubmissionId}/result`, { replace: true });
  }

  if (loading) {
    return (
      <section className="card">
        <h2>Đang tải bài thi</h2>
        <p className="muted">Đang lấy dữ liệu từ Backend API.</p>
      </section>
    );
  }

  if (loadError) {
    return (
      <section className="card">
        <h2>Không mở được bài thi</h2>
        <p className="error">{loadError}</p>
        <Link to="/exams">Quay lại danh sách ca thi</Link>
      </section>
    );
  }

  if (!payload) return null;

  if (runtimeState === 'requires_device_binding') {
    return (
      <RuntimeGateLayout
        payload={payload}
        runtimeState={runtimeState}
        answeredCount={answeredQuestionIds.size}
        totalQuestions={payload.paper.questions.length}
        remainingSeconds={remainingSeconds}
        isOnline={isOnline}
      >
        <DeviceBindingGate payload={payload} bindingBusy={bindingBusy} bindingError={bindingError} onBind={() => void handleBindDevice()} />
      </RuntimeGateLayout>
    );
  }

  if (runtimeState === 'ready_to_start' || runtimeState === 'starting') {
    return (
      <RuntimeGateLayout
        payload={payload}
        runtimeState={runtimeState}
        answeredCount={answeredQuestionIds.size}
        totalQuestions={payload.paper.questions.length}
        remainingSeconds={remainingSeconds}
        isOnline={isOnline}
      >
        <StartExamGate payload={payload} runtimeState={runtimeState} onStart={() => void handleStartExam()} />
      </RuntimeGateLayout>
    );
  }

  if (runtimeState === 'sealed') {
    return (
      <RuntimeGateLayout
        payload={payload}
        runtimeState={runtimeState}
        answeredCount={answeredQuestionIds.size}
        totalQuestions={payload.paper.questions.length}
        remainingSeconds={remainingSeconds}
        isOnline={isOnline}
      >
        <SubmissionSealedPanel submissionId={payload.submission.exam_submission_id} />
      </RuntimeGateLayout>
    );
  }

  if (runtimeState === 'closed_or_interrupted') {
    return (
      <RuntimeGateLayout
        payload={payload}
        runtimeState={runtimeState}
        answeredCount={answeredQuestionIds.size}
        totalQuestions={payload.paper.questions.length}
        remainingSeconds={remainingSeconds}
        isOnline={isOnline}
      >
        <UnsupportedRuntimePanel
          payload={payload}
          title="Phiên thi hiện không cho phép tiếp tục"
          summary="Ca thi đã đóng, bị chặn hoặc không còn ở trạng thái hợp lệ để tiếp tục làm bài. Giao diện không hiển thị vùng nhập liệu chỉnh sửa."
        />
      </RuntimeGateLayout>
    );
  }

  if (runtimeState === 'unsupported_runtime_mode') {
    return (
      <RuntimeGateLayout
        payload={payload}
        runtimeState={runtimeState}
        answeredCount={answeredQuestionIds.size}
        totalQuestions={payload.paper.questions.length}
        remainingSeconds={remainingSeconds}
        isOnline={isOnline}
      >
        <UnsupportedRuntimePanel
          payload={payload}
          title="Chế độ làm bài chưa được hỗ trợ"
          summary="Runtime này đang ở chế độ foundation-only, database, external hoặc chưa sẵn sàng. Nó phải tiếp tục là read-only và không được render thành workspace chỉnh sửa."
        />
      </RuntimeGateLayout>
    );
  }

  return (
    <section className="exam-taking-page student-exam-workspace">
      <ExamRuntimeHeader
        payload={payload}
        runtimeState={runtimeState}
        answeredCount={answeredQuestionIds.size}
        totalQuestions={payload.paper.questions.length}
        remainingSeconds={remainingSeconds}
        isOnline={isOnline}
        autosaveStatus={autosaveStatus}
        autosaveError={autosaveError}
        heartbeatError={heartbeatError}
        onSaveNow={() => void runAutosave()}
        saveDisabled={autosaveStatus === 'saving' || !isWorkspaceInteractive || dirtyQuestionIds.size === 0}
      />

      <RuntimeStatusBanner
        runtimeState={runtimeState}
        autosaveError={autosaveError}
        heartbeatError={heartbeatError}
        isOnline={isOnline}
      />

      <div className="exam-taking-layout">
        <main className="exam-paper-column">
          <section className="exam-guidance-panel" aria-label="Hướng dẫn làm bài">
            <h3>Hướng dẫn làm bài</h3>
            <ul>
              <li>Chỉ bấm Bắt đầu làm bài khi bạn đã sẵn sàng. Phiên thi không tự khởi động.</li>
              <li>Autosave chỉ phản ánh trạng thái đã được backend xác nhận. Offline hoặc lỗi mạng không hiển thị là đã lưu.</li>
              <li>Tệp bài làm được tải riêng qua upload API và chỉ hiện metadata khi backend đã chấp nhận.</li>
            </ul>
          </section>

          {hasVisualPaper && activePaperAsset ? <VisualPaperViewer asset={activePaperAsset} watermarkText={visualPaperWatermark} /> : null}

          {payload.paper.questions.length === 0 ? (
            <div className="empty-state">Đề thi chưa có câu hỏi.</div>
          ) : (
            <div className="question-list student-question-list">
              {questionItems.map((item) => {
                const questionId = item.question.generated_exam_question_id;
                const fileState = fileAnswers[questionId];
                const isCurrent = currentQuestionId === questionId;

                return (
                  <article
                    className={`question-card student-question-card${isCurrent ? ' is-current' : ''}`}
                    id={`question-${questionId}`}
                    key={questionId}
                    onFocusCapture={() => setCurrentQuestionId(questionId)}
                  >
                    <div className="question-card-heading">
                      <div>
                        <p className="eyebrow">Câu {item.question.question_order}</p>
                        <h3>{item.question.question_code || `Câu hỏi ${item.question.question_order}`}</h3>
                        <p className="question-text">{hasVisualPaper ? 'Nội dung câu hỏi được hiển thị trên tài liệu đề thi dạng ảnh/PDF.' : item.question.rendered_question_text}</p>
                      </div>
                      <div className="question-card-badges">
                        <span>{item.question.score} điểm</span>
                        <small className={`question-state ${item.navigatorTone}`}>
                          {item.isRequired && !item.isAnswered && item.mode !== 'INSTRUCTION_ONLY' && item.mode !== 'UNSUPPORTED'
                            ? `${item.navigatorLabel} · bắt buộc`
                            : item.navigatorLabel}
                        </small>
                      </div>
                    </div>

                    {item.mode === 'TEXT' ? (
                      <TextAnswerEditor
                        question={item.question}
                        answerLabel={item.answerLabel}
                        helperText={item.helperText}
                        value={answers[questionId] ?? ''}
                        onChange={(event) => handleAnswerChange(item.question, event)}
                        onFocus={() => setCurrentQuestionId(questionId)}
                        readOnly={isSealed || !isWorkspaceInteractive}
                        rows={item.answerType === 'SQL_TEXT' || item.answerType === 'CODE_TEXT' || item.answerType === 'JSON_TEXT' ? 10 : 6}
                      />
                    ) : null}

                    {item.mode === 'FILE_UPLOAD' ? (
                      <FileAnswerUploader
                        item={item}
                        state={fileState}
                        disabled={isSealed || !isWorkspaceInteractive}
                        onChooseFile={(event) => handleChooseFile(questionId, event)}
                        onUpload={() => void handleUploadFile(item.question)}
                        onFocus={() => setCurrentQuestionId(questionId)}
                      />
                    ) : null}

                    {item.mode === 'INSTRUCTION_ONLY' ? (
                      <div className="unsupported-question" role="note">
                        Câu hỏi này chỉ đọc theo hướng dẫn backend. Không có textbox, upload hoặc workspace tương tác ở pha này.
                      </div>
                    ) : null}

                    {item.mode === 'UNSUPPORTED' ? (
                      <div className="unsupported-question" role="note">
                        Loại câu hỏi này chưa được hỗ trợ trên giao diện hiện tại và sẽ không được render thành ô nhập liệu.
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          )}
        </main>

        <aside className="exam-side-panel" aria-label="Tổng quan bài thi">
          <div className="side-panel-section">
            <h3>Tổng quan</h3>
            <dl className="side-detail-list">
              <div>
                <dt>Ca thi</dt>
                <dd>{payload.session.session_code ? `Mã ${payload.session.session_code}` : `#${payload.session.exam_session_id}`}</dd>
              </div>
              <div>
                <dt>Runtime</dt>
                <dd>{runtimeStateLabel(runtimeState)}</dd>
              </div>
              <div>
                <dt>Số câu</dt>
                <dd>{payload.paper.questions.length}</dd>
              </div>
              <div>
                <dt>Đã trả lời</dt>
                <dd>{answeredQuestionIds.size}</dd>
              </div>
            </dl>
          </div>

          <QuestionNavigator
            questions={questionItems}
            currentQuestionId={currentQuestionId}
            onSelectQuestion={focusQuestion}
          />
        </aside>
      </div>

      <SealPreflightPanel
        phase={submitPhase}
        preflight={preflightResult}
        questionMap={questionMap}
        onConfirmSeal={() => void handleConfirmSeal()}
        onDismiss={resetSubmissionUi}
      />

      {submitError ? (
        <p className="form-error" role="alert">
          {submitError}
        </p>
      ) : null}

      <footer className="exam-taking-footer">
        <Link className="secondary-link" to="/exams">
          Quay lại danh sách
        </Link>
        <button
          className="primary-button"
          type="button"
          onClick={() => void handleSubmit()}
          disabled={submitPhase === 'checking_preflight' || submitPhase === 'sealing' || !isWorkspaceInteractive || hasPendingUploads}
        >
          {submitPhase === 'checking_preflight'
            ? 'Đang kiểm tra trước khi nộp...'
            : submitPhase === 'sealing'
              ? 'Đang nộp bài...'
              : isSealed
                ? 'Xem kết quả'
                : 'Nộp bài'}
        </button>
      </footer>
    </section>
  );
}
