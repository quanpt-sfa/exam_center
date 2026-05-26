import { httpRequest } from '../../../shared/api/httpClient';
import type {
  AttendanceMutationResult,
  CheckInAssignmentPayload,
  MarkAbsentPayload,
  ProctorAssignedRoom,
  ProctorAttendanceItem,
  ProctorAttendanceResponse,
  ProctorClosePreflightResponse,
  ProctorCloseRoomBlocker,
  ProctorCloseRoomCounts,
  ProctorCloseRoomRequest,
  ProctorCloseRoomResponse,
  ProctorIncident,
  ProctorIncidentCreatePayload,
  ProctorIncidentListResponse,
  ProctorIncidentUpdatePayload,
  ProctorRoomReadinessResponse,
  ProctorRoomRosterResponse,
  ScanCheckInPayload,
  ScanCheckInResult,
  StaleSessionRevokeResult,
  VerifyIdentityPayload,
  VerifyIdentityResult,
} from './contracts';

export class ProctorApiError extends Error {
  code: string;
  details?: unknown;

  constructor(message: string, code: string, details?: unknown) {
    super(message);
    this.name = 'ProctorApiError';
    this.code = code;
    this.details = details;
  }
}

type ApiListResponse<T> = {
  items: T[];
};

function asNumber(value: unknown): number {
  return Number(value);
}

function asNullableNumber(value: unknown): number | null {
  return value === null || value === undefined ? null : Number(value);
}

function asString(value: unknown): string {
  return String(value ?? '');
}

function asNullableString(value: unknown): string | null {
  return value === null || value === undefined ? null : String(value);
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};
}

function assertOk<T>(response: Awaited<ReturnType<typeof httpRequest<T>>>): T {
  if (!response.ok) {
    throw new ProctorApiError(response.error.message, response.error.code, response.error.details);
  }
  return response.data;
}

function normalizeAssignedRoom(value: unknown): ProctorAssignedRoom {
  const row = asRecord(value);
  return {
    exam_sitting_id: asNumber(row.exam_sitting_id),
    exam_sitting_room_id: asNumber(row.exam_sitting_room_id),
    room_id: asNumber(row.room_id),
    room_code: asString(row.room_code),
    room_name: asNullableString(row.room_name),
    sitting_code: asString(row.sitting_code),
    sitting_name: asString(row.sitting_name),
    sitting_status: asString(row.sitting_status),
    scheduled_start_at: asString(row.scheduled_start_at),
    scheduled_end_at: asString(row.scheduled_end_at),
    room_status: asString(row.room_status),
    capacity_allocated: asNullableNumber(row.capacity_allocated),
    assigned_student_count: asNumber(row.assigned_student_count ?? 0),
    assigned_station_count: asNumber(row.assigned_station_count ?? 0),
  };
}

function normalizeRosterItem(value: unknown) {
  const row = asRecord(value);
  return {
    exam_sitting_id: asNumber(row.exam_sitting_id),
    exam_sitting_room_id: asNumber(row.exam_sitting_room_id),
    room_code: asString(row.room_code),
    exam_assignment_id: asNumber(row.exam_assignment_id),
    station_id: asNumber(row.station_id),
    station_code: asString(row.station_code),
    student_id: asNumber(row.student_id),
    student_code: asString(row.student_code),
    full_name: asString(row.full_name),
    photo_ref: asNullableString(row.photo_ref),
    assignment_status: asString(row.assignment_status),
    station_assignment_status: asString(row.station_assignment_status),
    planned_device_id: asNullableNumber(row.planned_device_id),
    planned_device_asset_tag: asNullableString(row.planned_device_asset_tag),
    last_checkin_at: asNullableString(row.last_checkin_at),
    latest_health_status: asNullableString(row.latest_health_status),
    exam_session_id: asNullableNumber(row.exam_session_id),
    session_code: asNullableString(row.session_code),
    session_status: asNullableString(row.session_status),
    started_at: asNullableString(row.started_at),
    ended_at: asNullableString(row.ended_at),
    last_seen_at: asNullableString(row.last_seen_at),
    exam_submission_id: asNullableNumber(row.exam_submission_id),
    submission_status: asNullableString(row.submission_status),
    submitted_at: asNullableString(row.submitted_at),
    sealed_at: asNullableString(row.sealed_at),
  };
}

function normalizeRosterResponse(value: unknown): ProctorRoomRosterResponse {
  const row = asRecord(value);
  const items = Array.isArray(row.items) ? row.items.map(normalizeRosterItem) : [];
  return {
    exam_sitting_id: asNumber(row.exam_sitting_id),
    exam_sitting_room_id: asNumber(row.exam_sitting_room_id),
    room_code: asString(row.room_code),
    items,
  };
}

function normalizeAttendanceItem(value: unknown): ProctorAttendanceItem {
  const row = asRecord(value);
  return {
    exam_sitting_id: asNumber(row.exam_sitting_id),
    exam_sitting_room_id: asNumber(row.exam_sitting_room_id),
    room_code: asString(row.room_code),
    exam_assignment_id: asNumber(row.exam_assignment_id),
    station_assignment_id: asNullableNumber(row.station_assignment_id),
    station_id: asNullableNumber(row.station_id),
    station_code: asNullableString(row.station_code),
    student_id: asNumber(row.student_id),
    student_code: asString(row.student_code),
    full_name: asString(row.full_name),
    photo_url: asNullableString(row.photo_url),
    assignment_status: asString(row.assignment_status),
    station_assignment_status: asNullableString(row.station_assignment_status),
    latest_verification_status: asNullableString(row.latest_verification_status),
    latest_verification_method: asNullableString(row.latest_verification_method),
    latest_verified_at: asNullableString(row.latest_verified_at),
    latest_verified_by: asNullableNumber(row.latest_verified_by),
    checked_in_at: asNullableString(row.checked_in_at),
    checked_in_by: asNullableNumber(row.checked_in_by),
    latest_attendance_note: asNullableString(row.latest_attendance_note),
    exam_session_id: asNullableNumber(row.exam_session_id),
    session_status: asNullableString(row.session_status),
    submission_status: asNullableString(row.submission_status),
    last_seen_at: asNullableString(row.last_seen_at),
  };
}

function normalizeAttendanceResponse(value: unknown): ProctorAttendanceResponse {
  const row = asRecord(value);
  const items = Array.isArray(row.items) ? row.items.map(normalizeAttendanceItem) : [];
  return {
    exam_sitting_id: asNumber(row.exam_sitting_id),
    exam_sitting_room_id: asNumber(row.exam_sitting_room_id),
    room_code: asString(row.room_code),
    items,
  };
}

function normalizeVerifyIdentityResult(value: unknown): VerifyIdentityResult {
  const row = asRecord(value);
  return {
    checkin_verification_id: asNumber(row.checkin_verification_id),
    exam_sitting_room_id: asNumber(row.exam_sitting_room_id),
    exam_assignment_id: asNumber(row.exam_assignment_id),
    station_assignment_id: asNullableNumber(row.station_assignment_id),
    exam_session_id: asNullableNumber(row.exam_session_id),
    verification_status: asString(row.verification_status),
    verification_method: asString(row.verification_method),
    verified_at: asNullableString(row.verified_at),
    verified_by: asNullableNumber(row.verified_by),
    note: asNullableString(row.note),
    metadata_json: row.metadata_json == null ? null : asRecord(row.metadata_json),
  };
}

function normalizeScanCheckInResult(value: unknown): ScanCheckInResult {
  const row = asRecord(value);
  return {
    ...normalizeAttendanceItem(value),
    scan_match_type: asString(row.scan_match_type),
  };
}

function normalizeReadinessCheck(value: unknown) {
  const row = asRecord(value);
  return {
    station_code: asNullableString(row.station_code),
    asset_tag: asNullableString(row.asset_tag),
    last_checkin_at: asNullableString(row.last_checkin_at),
    health_status: asNullableString(row.health_status),
    mismatch: Boolean(row.mismatch),
  };
}

function normalizeReadinessResponse(value: unknown): ProctorRoomReadinessResponse {
  const row = asRecord(value);
  const items = Array.isArray(row.items) ? row.items.map(normalizeReadinessCheck) : [];
  return {
    exam_sitting_id: asNumber(row.exam_sitting_id),
    exam_sitting_room_id: asNumber(row.exam_sitting_room_id),
    room_code: asString(row.room_code),
    items,
  };
}

function normalizeIncident(value: unknown): ProctorIncident {
  const row = asRecord(value);
  return {
    incident_id: asNumber(row.incident_id),
    exam_sitting_id: asNumber(row.exam_sitting_id),
    exam_sitting_room_id: asNullableNumber(row.exam_sitting_room_id),
    exam_assignment_id: asNullableNumber(row.exam_assignment_id),
    exam_session_id: asNullableNumber(row.exam_session_id),
    station_id: asNullableNumber(row.station_id),
    device_id: asNullableNumber(row.device_id),
    incident_type: asString(row.incident_type),
    incident_status: asString(row.incident_status),
    reported_by: asNullableNumber(row.reported_by),
    reported_at: asString(row.reported_at),
    resolved_by: asNullableNumber(row.resolved_by),
    resolved_at: asNullableString(row.resolved_at),
    updated_by: asNullableNumber(row.updated_by),
    updated_at: asNullableString(row.updated_at),
    resolution_note: asNullableString(row.resolution_note),
    description: asNullableString(row.description),
    metadata_json: asRecord(row.metadata_json),
  };
}

function buildProctorIncidentUpdateBody(payload: ProctorIncidentUpdatePayload): string {
  const body: Record<string, unknown> = {};

  if ('incident_status' in payload) {
    body.incident_status = payload.incident_status;
  }
  if ('description' in payload) {
    body.description = payload.description;
  }
  if ('resolution_note' in payload) {
    body.resolution_note = payload.resolution_note;
  }

  return JSON.stringify(body);
}

function normalizeIncidentListResponse(value: unknown): ProctorIncidentListResponse {
  const row = asRecord(value);
  const items = Array.isArray(row.items) ? row.items.map(normalizeIncident) : [];
  return { items };
}

function normalizeCloseRoomBlocker(value: unknown): ProctorCloseRoomBlocker {
  const row = asRecord(value);
  const details = Array.isArray(row.details) ? row.details.map(asRecord) : null;
  return {
    code: asString(row.code) as ProctorCloseRoomBlocker['code'],
    severity: asString(row.severity) as ProctorCloseRoomBlocker['severity'],
    message: asString(row.message),
    count: asNumber(row.count ?? 0),
    details,
  };
}

function normalizeCloseRoomCounts(value: unknown): ProctorCloseRoomCounts {
  const row = asRecord(value);
  return {
    total_assignments: asNumber(row.total_assignments ?? 0),
    checked_in_count: asNumber(row.checked_in_count ?? 0),
    absent_count: asNumber(row.absent_count ?? 0),
    pending_attendance_count: asNumber(row.pending_attendance_count ?? 0),
    open_incident_count: asNumber(row.open_incident_count ?? 0),
    in_progress_incident_count: asNumber(row.in_progress_incident_count ?? 0),
    active_session_count: asNumber(row.active_session_count ?? 0),
    interrupted_session_count: asNumber(row.interrupted_session_count ?? 0),
    pending_submission_count: asNumber(row.pending_submission_count ?? 0),
    stale_heartbeat_count: asNumber(row.stale_heartbeat_count ?? 0),
  };
}

function normalizeClosePreflightResponse(value: unknown): ProctorClosePreflightResponse {
  const row = asRecord(value);
  const blockers = Array.isArray(row.blockers) ? row.blockers.map(normalizeCloseRoomBlocker) : [];
  const warnings = Array.isArray(row.warnings) ? row.warnings.map(normalizeCloseRoomBlocker) : [];
  return {
    exam_sitting_room_id: asNumber(row.exam_sitting_room_id),
    room_code: asNullableString(row.room_code),
    room_status: asString(row.room_status) as ProctorClosePreflightResponse['room_status'],
    can_close: Boolean(row.can_close),
    blockers,
    warnings,
    counts: normalizeCloseRoomCounts(row.counts),
    generated_at: asString(row.generated_at),
  };
}

function normalizeCloseRoomResponse(value: unknown): ProctorCloseRoomResponse {
  const row = asRecord(value);
  const blockers = Array.isArray(row.blockers) ? row.blockers.map(normalizeCloseRoomBlocker) : [];
  return {
    status: asString(row.status) as ProctorCloseRoomResponse['status'],
    exam_sitting_room_id: asNumber(row.exam_sitting_room_id),
    previous_status: asNullableString(row.previous_status) as ProctorCloseRoomResponse['previous_status'],
    new_status: asString(row.new_status),
    closed_at: asNullableString(row.closed_at),
    closed_by: asNullableNumber(row.closed_by),
    close_summary: asRecord(row.close_summary),
    blockers,
  };
}

export async function listMySittingRooms(): Promise<ProctorAssignedRoom[]> {
  const data = assertOk(await httpRequest<ApiListResponse<unknown>>('/proctor/my-sitting-rooms'));
  return Array.isArray(data.items) ? data.items.map(normalizeAssignedRoom) : [];
}

export async function getProctorRoomRoster(examSittingRoomId: number): Promise<ProctorRoomRosterResponse> {
  const data = assertOk(await httpRequest<unknown>(`/proctor/sitting-rooms/${examSittingRoomId}/roster`));
  return normalizeRosterResponse(data);
}

export async function listProctorRoomAttendance(examSittingRoomId: number): Promise<ProctorAttendanceResponse> {
  const data = assertOk(await httpRequest<unknown>(`/proctor/sitting-rooms/${examSittingRoomId}/attendance`));
  return normalizeAttendanceResponse(data);
}

export async function checkInAssignment(
  examSittingRoomId: number,
  examAssignmentId: number,
  payload: CheckInAssignmentPayload
): Promise<AttendanceMutationResult> {
  const data = assertOk(
    await httpRequest<unknown>(`/proctor/sitting-rooms/${examSittingRoomId}/assignments/${examAssignmentId}/check-in`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  );
  return normalizeAttendanceItem(data);
}

export async function markAssignmentAbsent(
  examSittingRoomId: number,
  examAssignmentId: number,
  payload: MarkAbsentPayload
): Promise<AttendanceMutationResult> {
  const data = assertOk(
    await httpRequest<unknown>(`/proctor/sitting-rooms/${examSittingRoomId}/assignments/${examAssignmentId}/mark-absent`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  );
  return normalizeAttendanceItem(data);
}

export async function verifyAssignmentIdentity(
  examSittingRoomId: number,
  examAssignmentId: number,
  payload: VerifyIdentityPayload
): Promise<VerifyIdentityResult> {
  const data = assertOk(
    await httpRequest<unknown>(`/proctor/sitting-rooms/${examSittingRoomId}/assignments/${examAssignmentId}/verify-identity`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  );
  return normalizeVerifyIdentityResult(data);
}

export async function scanCheckInAttendance(
  examSittingRoomId: number,
  payload: ScanCheckInPayload
): Promise<ScanCheckInResult> {
  const data = assertOk(
    await httpRequest<unknown>(`/proctor/sitting-rooms/${examSittingRoomId}/attendance/scan-check-in`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  );
  return normalizeScanCheckInResult(data);
}

export async function getProctorRoomReadiness(examSittingRoomId: number): Promise<ProctorRoomReadinessResponse> {
  const data = assertOk(await httpRequest<unknown>(`/proctor/sitting-rooms/${examSittingRoomId}/readiness`));
  return normalizeReadinessResponse(data);
}

export async function getProctorRoomClosePreflight(examSittingRoomId: number): Promise<ProctorClosePreflightResponse> {
  const data = assertOk(await httpRequest<unknown>(`/proctor/sitting-rooms/${examSittingRoomId}/close-preflight`));
  return normalizeClosePreflightResponse(data);
}

export async function closeProctorRoom(
  examSittingRoomId: number,
  payload: ProctorCloseRoomRequest
): Promise<ProctorCloseRoomResponse> {
  const data = assertOk(
    await httpRequest<unknown>(`/proctor/sitting-rooms/${examSittingRoomId}/close`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  );
  return normalizeCloseRoomResponse(data);
}

export async function listProctorRoomIncidents(
  examSittingRoomId: number,
  params?: { limit?: number; offset?: number }
): Promise<ProctorIncident[]> {
  const queryParams = new URLSearchParams();
  if (params?.limit !== undefined) {
    queryParams.set('limit', String(params.limit));
  }
  if (params?.offset !== undefined) {
    queryParams.set('offset', String(params.offset));
  }
  const query = queryParams.toString();
  const path = query
    ? `/proctor/sitting-rooms/${examSittingRoomId}/incidents?${query}`
    : `/proctor/sitting-rooms/${examSittingRoomId}/incidents`;
  const data = assertOk(await httpRequest<unknown>(path));
  return normalizeIncidentListResponse(data).items;
}

export async function createProctorIncident(examSittingRoomId: number, payload: ProctorIncidentCreatePayload): Promise<ProctorIncident> {
  const data = assertOk(
    await httpRequest<unknown>(`/proctor/sitting-rooms/${examSittingRoomId}/incidents`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  );
  return normalizeIncident(data);
}

export async function updateProctorIncident(incidentId: number, payload: ProctorIncidentUpdatePayload): Promise<ProctorIncident> {
  const data = assertOk(
    await httpRequest<unknown>(`/proctor/incidents/${incidentId}`, {
      method: 'PATCH',
      body: buildProctorIncidentUpdateBody(payload),
    })
  );
  return normalizeIncident(data);
}

export async function revokeStudentStaleSession(examSittingRoomId: number, studentId: number): Promise<StaleSessionRevokeResult> {
  const data = assertOk(
    await httpRequest<StaleSessionRevokeResult>(`/delivery/exam-sitting-rooms/${examSittingRoomId}/students/${studentId}/revoke-stale-session`, {
      method: 'POST',
    })
  );
  return data;
}
