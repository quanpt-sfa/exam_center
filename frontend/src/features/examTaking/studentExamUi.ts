type StudentExamUiInput = {
  submissionStatus?: string | null;
  sessionStatus?: string | null;
  isOpen?: boolean | null;
  hasResult?: boolean | null;
};

const STARTABLE_SESSION_STATUSES = new Set(['CREATED', 'WAITING_FOR_CHECKIN', 'READY_TO_START', 'PAUSED', 'INTERRUPTED', 'ASSIGNED']);
const ACTIVE_SESSION_STATUSES = new Set(['STARTED', 'IN_PROGRESS']);
const TERMINAL_SESSION_STATUSES = new Set(['COMPLETED', 'CANCELLED']);
const TERMINAL_SUBMISSION_STATUSES = new Set(['SEALED', 'SUBMITTED', 'GRADED', 'COMPLETED']);

function normalizeStatus(value?: string | null): string {
  return String(value || '').trim().toUpperCase();
}

export function isCompletedStudentExam(input: StudentExamUiInput): boolean {
  return TERMINAL_SUBMISSION_STATUSES.has(normalizeStatus(input.submissionStatus)) || TERMINAL_SESSION_STATUSES.has(normalizeStatus(input.sessionStatus));
}

export function isLiveStudentExam(input: StudentExamUiInput): boolean {
  if (ACTIVE_SESSION_STATUSES.has(normalizeStatus(input.sessionStatus)) || ACTIVE_SESSION_STATUSES.has(normalizeStatus(input.submissionStatus))) {
    return true;
  }

  return Boolean(input.isOpen) && !isCompletedStudentExam(input) && !STARTABLE_SESSION_STATUSES.has(normalizeStatus(input.submissionStatus));
}

export function isReadyStudentExam(input: StudentExamUiInput): boolean {
  if (STARTABLE_SESSION_STATUSES.has(normalizeStatus(input.sessionStatus)) || STARTABLE_SESSION_STATUSES.has(normalizeStatus(input.submissionStatus))) {
    return true;
  }

  return Boolean(input.isOpen) && !isCompletedStudentExam(input) && !isLiveStudentExam(input);
}

export function isActionableStudentExam(input: StudentExamUiInput): boolean {
  return !isCompletedStudentExam(input) && (isLiveStudentExam(input) || isReadyStudentExam(input));
}

export function getStudentExamStatusLabel(input: StudentExamUiInput): string {
  if (isCompletedStudentExam(input)) {
    return 'Đã hoàn thành';
  }

  if (isLiveStudentExam(input)) {
    return 'Đang mở';
  }

  if (isReadyStudentExam(input)) {
    return 'Sẵn sàng vào thi';
  }

  if (input.isOpen === false) {
    return 'Chưa mở';
  }

  return 'Chưa có bài thi';
}

export function getStudentExamActionLabel(input: StudentExamUiInput): string {
  if (isCompletedStudentExam(input)) {
    return input.hasResult ? 'Xem kết quả' : 'Xem trạng thái';
  }

  if (isLiveStudentExam(input)) {
    return 'Tiếp tục làm bài';
  }

  if (isReadyStudentExam(input)) {
    return 'Vào bài thi';
  }

  return 'Mở ca thi';
}