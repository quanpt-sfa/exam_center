export type ProctorAssignedRoom = {
  exam_sitting_id: number;
  exam_sitting_room_id: number;
  room_id: number;
  room_code: string;
  room_name: string | null;
  sitting_code: string;
  sitting_name: string;
  sitting_status: string;
  scheduled_start_at: string;
  scheduled_end_at: string;
  room_status: string;
  capacity_allocated: number | null;
  assigned_student_count: number;
  assigned_station_count: number;
};

export type ProctorRoomRosterItem = {
  exam_sitting_id: number;
  exam_sitting_room_id: number;
  room_code: string;
  exam_assignment_id: number;
  station_id: number;
  station_code: string;
  student_id: number;
  student_code: string;
  full_name: string;
  photo_ref: string | null;
  assignment_status: string;
  station_assignment_status: string;
  planned_device_id: number | null;
  planned_device_asset_tag: string | null;
  last_checkin_at: string | null;
  latest_health_status: string | null;
  exam_session_id: number | null;
  session_code: string | null;
  session_status: string | null;
  started_at: string | null;
  ended_at: string | null;
  last_seen_at: string | null;
  exam_submission_id: number | null;
  submission_status: string | null;
  submitted_at: string | null;
  sealed_at: string | null;
};

export type ProctorRoomRosterResponse = {
  exam_sitting_id: number;
  exam_sitting_room_id: number;
  room_code: string;
  items: ProctorRoomRosterItem[];
};

export type AttendanceAssignmentStatus =
  | 'ASSIGNED'
  | 'CHECKED_IN'
  | 'ABSENT'
  | 'CANCELLED'
  | 'RESCHEDULED'
  | 'VOIDED'
  | 'COMPLETED';

export type AttendanceStationAssignmentStatus = 'ASSIGNED' | 'CHECKED_IN' | 'TRANSFERRED' | 'CANCELLED' | 'NO_SHOW';

export type AttendanceVerificationStatus = 'VERIFIED' | 'REJECTED';
export type AttendanceVerificationMethod = 'PHOTO_ID' | 'MANUAL' | 'OTHER';
export type ManualCheckInMethod = 'MANUAL';
export type ScanCheckInMethod = 'BARCODE' | 'MAGSTRIPE' | 'QR_CODE';
export type ScanMatchType = 'STUDENT_CODE' | 'EXAM_ASSIGNMENT_ID';

export type ProctorAttendanceItem = {
  exam_sitting_id: number;
  exam_sitting_room_id: number;
  room_code: string;
  exam_assignment_id: number;
  station_assignment_id: number | null;
  station_id: number | null;
  station_code: string | null;
  student_id: number;
  student_code: string;
  full_name: string;
  photo_url: string | null;
  assignment_status: string;
  station_assignment_status: string | null;
  latest_verification_status: string | null;
  latest_verification_method: string | null;
  latest_verified_at: string | null;
  latest_verified_by: number | null;
  checked_in_at: string | null;
  checked_in_by: number | null;
  latest_attendance_note: string | null;
  exam_session_id: number | null;
  session_status: string | null;
  submission_status: string | null;
  last_seen_at: string | null;
};

export type ProctorAttendanceResponse = {
  exam_sitting_id: number;
  exam_sitting_room_id: number;
  room_code: string;
  items: ProctorAttendanceItem[];
};

export type CheckInAssignmentPayload = {
  checkin_method?: ManualCheckInMethod;
  scan_device_id?: string | null;
  note?: string | null;
  context_json?: Record<string, unknown> | null;
};

export type AttendanceMutationResult = ProctorAttendanceItem;

export type MarkAbsentPayload = {
  note: string;
  reason_code?: string | null;
  context_json?: Record<string, unknown> | null;
};

export type VerifyIdentityPayload = {
  verification_status: AttendanceVerificationStatus;
  verification_method: AttendanceVerificationMethod;
  note?: string | null;
  metadata_json?: Record<string, unknown> | null;
};

export type VerifyIdentityResult = {
  checkin_verification_id: number;
  exam_sitting_room_id: number;
  exam_assignment_id: number;
  station_assignment_id: number | null;
  exam_session_id: number | null;
  verification_status: string;
  verification_method: string;
  verified_at: string | null;
  verified_by: number | null;
  note: string | null;
  metadata_json: Record<string, unknown> | null;
};

export type ScanCheckInPayload = {
  checkin_method: ScanCheckInMethod;
  scan_value: string;
  scan_device_id?: string | null;
  note?: string | null;
  context_json?: Record<string, unknown> | null;
};

export type ScanCheckInResult = ProctorAttendanceItem & {
  scan_match_type: string;
};

export type ProctorRoomReadinessCheck = {
  station_code: string | null;
  asset_tag: string | null;
  last_checkin_at: string | null;
  health_status: string | null;
  mismatch: boolean;
};

export type ProctorRoomReadinessResponse = {
  exam_sitting_id: number;
  exam_sitting_room_id: number;
  room_code: string;
  items: ProctorRoomReadinessCheck[];
};

export type ProctorIncident = {
  incident_id: number;
  exam_sitting_id: number;
  exam_sitting_room_id: number | null;
  exam_assignment_id: number | null;
  exam_session_id: number | null;
  station_id: number | null;
  device_id: number | null;
  incident_type: string;
  incident_status: string;
  reported_by: number | null;
  reported_at: string;
  resolved_by: number | null;
  resolved_at: string | null;
  updated_by: number | null;
  updated_at: string | null;
  resolution_note: string | null;
  description: string | null;
  metadata_json: Record<string, unknown>;
};

export type ProctorIncidentListResponse = {
  items: ProctorIncident[];
};

export type ProctorIncidentCreatePayload = {
  exam_assignment_id?: number | null;
  station_id?: number | null;
  device_id?: number | null;
  incident_type: string;
  description?: string | null;
  metadata_json?: Record<string, unknown> | null;
};

export type ProctorIncidentUpdatePayload = {
  incident_status?: string | null;
  description?: string | null;
  resolution_note?: string | null;
};

export type StaleSessionRevokeResult = {
  status: 'revoked' | 'no_active_session';
};

export type ProctorPollingState = {
  is_refreshing: boolean;
  last_updated_at: string | null;
  interval_ms: number;
};

export type ProctorCloseSeverity = 'hard' | 'warning' | (string & {});

export type ProctorCloseBlockerCode =
  | 'ROOM_ALREADY_CLOSED'
  | 'ROOM_NOT_CLOSEABLE'
  | 'ATTENDANCE_INCOMPLETE'
  | 'INCIDENTS_UNRESOLVED'
  | 'ACTIVE_SESSIONS'
  | 'INTERRUPTED_SESSIONS'
  | 'SUBMISSIONS_PENDING'
  | 'STALE_HEARTBEATS'
  | (string & {});

export type ProctorCloseRoomStatus =
  | 'PLANNED'
  | 'READY'
  | 'OPEN'
  | 'CLOSED'
  | 'CANCELLED'
  | (string & {});

export type ProctorCloseRoomBlocker = {
  code: ProctorCloseBlockerCode;
  severity: ProctorCloseSeverity;
  message: string;
  count: number;
  details: Array<Record<string, unknown>> | null;
};

export type ProctorCloseRoomCounts = {
  total_assignments: number;
  checked_in_count: number;
  absent_count: number;
  pending_attendance_count: number;
  open_incident_count: number;
  in_progress_incident_count: number;
  active_session_count: number;
  interrupted_session_count: number;
  pending_submission_count: number;
  stale_heartbeat_count: number;
};

export type ProctorClosePreflightResponse = {
  exam_sitting_room_id: number;
  room_code: string | null;
  room_status: ProctorCloseRoomStatus;
  can_close: boolean;
  blockers: ProctorCloseRoomBlocker[];
  warnings: ProctorCloseRoomBlocker[];
  counts: ProctorCloseRoomCounts;
  generated_at: string;
};

export type ProctorCloseRoomRequest = {
  close_note: string | null;
  confirm_no_blockers: boolean;
  context_json?: {
    ui_source?: string | null;
    client_request_id?: string | null;
  } | null;
};

export type ProctorCloseRoomResponse = {
  status: 'closed' | 'already_closed' | 'blocked' | (string & {});
  exam_sitting_room_id: number;
  previous_status: ProctorCloseRoomStatus | null;
  new_status: ProctorCloseRoomStatus | string;
  closed_at: string | null;
  closed_by: number | null;
  close_summary: Record<string, unknown>;
  blockers: ProctorCloseRoomBlocker[];
};
