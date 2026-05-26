import type { ProctorRoomReadinessCheck, ProctorRoomRosterItem } from './api/contracts';

function normalized(value?: string | null): string {
  return String(value || '').trim().toUpperCase();
}

function unknownLabel(raw?: string | null): string {
  const value = String(raw || '').trim();
  if (!value) {
    return 'Không xác định';
  }
  return `Không xác định: ${value}`;
}

const PROCTOR_INCIDENT_TRANSITIONS: Record<string, readonly string[]> = {
  OPEN: ['IN_PROGRESS', 'RESOLVED'],
  IN_PROGRESS: ['RESOLVED'],
  RESOLVED: [],
  VOIDED: [],
};

export function formatDateTime(value?: string | null): string {
  if (!value) {
    return '-';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: '2-digit',
  }).format(parsed);
}

export function sessionStatusLabel(status?: string | null): string {
  const value = normalized(status);
  switch (value) {
    case 'IN_PROGRESS':
      return 'Đang thi';
    case 'STARTED':
    case 'RUNNING':
      return 'Đã bắt đầu';
    case 'PAUSED':
      return 'Tạm dừng';
    case 'INTERRUPTED':
      return 'Gián đoạn';
    case 'COMPLETED':
      return 'Hoàn tất';
    case 'ASSIGNED':
      return 'Đã gán';
    case 'UNKNOWN':
    case '':
      return 'Không xác định';
    default:
      return unknownLabel(status);
  }
}

export function submissionStatusLabel(status?: string | null): string {
  const value = normalized(status);
  switch (value) {
    case 'IN_PROGRESS':
      return 'Đang làm bài';
    case 'SUBMITTED':
      return 'Đã nộp';
    case 'SEALED':
      return 'Đã niêm phong';
    case 'GRADED':
      return 'Đã chấm';
    case 'FINALIZED':
      return 'Đã hoàn tất';
    case 'PENDING':
    case '':
    case 'UNKNOWN':
      return 'Chưa có';
    default:
      return unknownLabel(status);
  }
}

export function readinessStatusLabel(status?: string | null): string {
  const value = normalized(status);
  switch (value) {
    case 'READY':
      return 'Sẵn sàng';
    case 'WARNING':
      return 'Cảnh báo';
    case 'ERROR':
      return 'Lỗi';
    case 'UNKNOWN':
    case '':
      return 'Không xác định';
    default:
      return unknownLabel(status);
  }
}

export function incidentTypeLabel(type?: string | null): string {
  const value = normalized(type);
  switch (value) {
    case 'DEVICE_FAILURE':
      return 'Lỗi thiết bị';
    case 'NETWORK_FAILURE':
      return 'Lỗi mạng';
    case 'POWER_FAILURE':
      return 'Mất điện';
    case 'LOGIN_ISSUE':
      return 'Lỗi đăng nhập';
    case 'IDENTITY_MISMATCH':
      return 'Sai lệch định danh';
    case 'ADMIN_NOTE':
      return 'Ghi chú quản trị';
    default:
      return unknownLabel(type);
  }
}

export function incidentStatusLabel(status?: string | null): string {
  const value = normalized(status);
  switch (value) {
    case 'OPEN':
      return 'Đang mở';
    case 'IN_PROGRESS':
      return 'Đang xử lý';
    case 'RESOLVED':
      return 'Đã xử lý';
    case 'VOIDED':
      return 'Đã vô hiệu';
    case 'UNKNOWN':
    case '':
      return 'Không xác định';
    default:
      return unknownLabel(status);
  }
}

export function getAllowedProctorIncidentTransitions(status?: string | null): string[] {
  const value = normalized(status);
  return [...(PROCTOR_INCIDENT_TRANSITIONS[value] ?? [])];
}

export function canProctorResolveIncident(status?: string | null): boolean {
  return getAllowedProctorIncidentTransitions(status).includes('RESOLVED');
}

export function isIncidentTerminal(status?: string | null): boolean {
  const value = normalized(status);
  return value === 'RESOLVED' || value === 'VOIDED';
}

export function requiresResolutionNoteForTransition(fromStatus?: string | null, toStatus?: string | null): boolean {
  const fromValue = normalized(fromStatus);
  const toValue = normalized(toStatus);
  if (toValue !== 'RESOLVED') {
    return false;
  }
  return getAllowedProctorIncidentTransitions(fromValue).includes('RESOLVED');
}

export function assignmentStatusLabel(status?: string | null): string {
  const value = normalized(status);
  switch (value) {
    case 'ASSIGNED':
      return 'Đã phân công';
    case 'CHECKED_IN':
      return 'Đã check-in';
    case 'ABSENT':
      return 'Vắng';
    case 'RESCHEDULED':
      return 'Đổi lịch';
    case 'VOIDED':
      return 'Vô hiệu';
    case 'COMPLETED':
      return 'Hoàn tất';
    default:
      return unknownLabel(status);
  }
}

export function stationAssignmentStatusLabel(status?: string | null): string {
  const value = normalized(status);
  switch (value) {
    case 'ASSIGNED':
      return 'Đã gán máy';
    case 'CHECKED_IN':
      return 'Đã vào chỗ';
    case 'TRANSFERRED':
      return 'Đã chuyển máy';
    case 'NO_SHOW':
      return 'Không có mặt';
    case 'CANCELLED':
      return 'Đã hủy';
    default:
      return unknownLabel(status);
  }
}

export function verificationStatusLabel(status?: string | null): string {
  const value = normalized(status);
  switch (value) {
    case 'VERIFIED':
      return 'Đã xác minh';
    case 'REJECTED':
      return 'Từ chối';
    case '':
    case 'UNKNOWN':
      return 'Chưa xác minh';
    default:
      return unknownLabel(status);
  }
}

export function verificationMethodLabel(method?: string | null): string {
  const value = normalized(method);
  switch (value) {
    case 'PHOTO_ID':
      return 'Ảnh/giấy tờ';
    case 'MANUAL':
      return 'Thủ công';
    case 'OTHER':
      return 'Khác';
    case '':
    case 'UNKNOWN':
      return 'Chưa có';
    default:
      return unknownLabel(method);
  }
}

export type CandidateProgress = 'not_started' | 'in_progress' | 'submitted' | 'interrupted';

export function hasTerminalSubmissionState(item: ProctorRoomRosterItem): boolean {
  const submissionStatus = normalized(item.submission_status);
  return Boolean(item.sealed_at || item.submitted_at || ['SUBMITTED', 'SEALED', 'GRADED', 'FINALIZED'].includes(submissionStatus));
}

export function resolveCandidateProgress(item: ProctorRoomRosterItem): CandidateProgress {
  const submissionStatus = normalized(item.submission_status);
  const sessionStatus = normalized(item.session_status);

  if (hasTerminalSubmissionState(item)) {
    return 'submitted';
  }

  if (['INTERRUPTED'].includes(sessionStatus)) {
    return 'interrupted';
  }

  if (['IN_PROGRESS', 'STARTED', 'RUNNING', 'PAUSED'].includes(sessionStatus) || item.started_at) {
    return 'in_progress';
  }

  return 'not_started';
}

export function deriveRosterSummary(items: ProctorRoomRosterItem[]) {
  return items.reduce(
    (summary, item) => {
      summary.total += 1;
      const progress = resolveCandidateProgress(item);
      summary[progress] += 1;
      if (item.last_seen_at) {
        summary.hasLastSeen = true;
      }
      return summary;
    },
    {
      total: 0,
      not_started: 0,
      in_progress: 0,
      submitted: 0,
      interrupted: 0,
      hasLastSeen: false,
    }
  );
}

export function deriveReadinessSummary(items: ProctorRoomReadinessCheck[]) {
  return items.reduce(
    (summary, item) => {
      summary.total += 1;
      const status = normalized(item.health_status);
      if (status === 'READY') {
        summary.ready += 1;
      } else if (status === 'WARNING') {
        summary.warning += 1;
      } else if (status === 'ERROR') {
        summary.error += 1;
      } else {
        summary.unknown += 1;
      }
      if (item.mismatch) {
        summary.mismatch += 1;
      }
      return summary;
    },
    { total: 0, ready: 0, warning: 0, error: 0, unknown: 0, mismatch: 0 }
  );
}
