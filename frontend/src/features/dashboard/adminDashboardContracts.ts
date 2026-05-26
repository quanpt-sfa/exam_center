export type DashboardSeverity = 'critical' | 'warning' | 'info' | (string & {});

export type DashboardAlertType =
  | 'INCIDENT'
  | 'CLOSE_ROOM_BLOCKED'
  | 'SETUP_BLOCKER_NO_PUBLISHED_EXAM'
  | 'SETUP_BLOCKER_NOT_PREPARED'
  | 'SESSION_STALE'
  | 'SESSION_INTERRUPTED'
  | (string & {});

export type AdminDashboardCountGroup = Record<string, number>;

export type AdminDashboardSummary = {
  generated_at: string;
  sittings: {
    today: number;
    open: number;
    upcoming_24h: number;
    not_ready: number;
  };
  setup: {
    sittings_without_published_exam: number;
    sittings_not_prepared: number;
    rooms_missing_proctors: number;
    rooms_missing_ready_stations: number;
    students_unassigned: number;
    failed_import_jobs: number;
  };
  live: {
    open_rooms: number;
    checked_in: number;
    not_checked_in: number;
    started: number;
    checked_in_not_started: number;
    not_started_in_open_sittings: number;
    interrupted: number;
    sealed: number;
  };
  incidents: {
    open: number;
    in_progress: number;
    resolved_today: number;
  };
  close_room: {
    blocked_rooms: number;
    closed_rooms: number;
  };
  grading: {
    pending: number;
    running: number;
    computed: number;
    needs_review: number;
    failed: number;
  };
  system: {
    active_user_sessions: number;
    locked_accounts: number;
    workers_unhealthy: number;
  };
};

export type AdminDashboardAlert = {
  alert_id: string;
  type: DashboardAlertType;
  severity: DashboardSeverity;
  title: string;
  description: string;
  entity_type: string;
  entity_id: string;
  exam_sitting_id: number | null;
  exam_sitting_room_id: number | null;
  action_route: string | null;
  created_at: string;
  status: string;
};

export type AdminDashboardAlertsResponse = {
  generated_at: string;
  items: AdminDashboardAlert[];
  limit: number;
};

export type AdminDashboardApiError = {
  code: string;
  message: string;
  details: unknown;
  request_id: string | null;
  status: number;
};
