export type ProcessingOverallStatus =
  | 'NOT_FOUND'
  | 'DRAFT_OR_UNSEALED'
  | 'SEALED'
  | 'WAITING_CAPTURE'
  | 'CAPTURING'
  | 'CAPTURE_FAILED'
  | 'WAITING_GRADING'
  | 'GRADING'
  | 'GRADING_FAILED'
  | 'COMPLETED'
  | 'NEEDS_REVIEW';

export interface ProcessingSealStatus {
  submission_seal_id: number | null;
  seal_status: string | null;
  sealed_at: string | null;
  sealed_answer_count: number;
  has_sealed_answer: boolean;
}

export interface ProcessingCaptureStatus {
  required: boolean;
  status: string | null;
  capture_job_id: number | null;
  capture_profile_id: number | null;
  artifact_count: number;
  dataset_count: number;
  latest_event_type: string | null;
  latest_error_code: string | null;
  latest_error_message_sanitized: string | null;
}

export interface ProcessingGradingStatus {
  grading_job_id: number | null;
  grading_job_status: string | null;
  grading_run_id: number | null;
  grading_run_status: string | null;
  worker_id: string | null;
  claimed_at: string | null;
  finished_at: string | null;
  latest_event_type: string | null;
}

export interface ProcessingTaskSummary {
  total: number;
  queued: number;
  running: number;
  waiting_capture: number;
  completed: number;
  failed: number;
  needs_review: number;
  by_input_source: Record<string, number>;
  by_answer_language: Record<string, number>;
}

export interface ProcessingResultSummary {
  actual_result_count: number;
  comparison_count: number;
  question_score_count: number;
}

export interface ProcessingScoreSummary {
  submission_score_id: number | null;
  total_score: number | null;
  max_score: number | null;
  score_status: string | null;
  finalized_at: string | null;
}

export interface ProcessingTimestamps {
  created_at: string | null;
  updated_at: string | null;
  latest_activity_at: string | null;
}

export interface ProcessingStatusResponse {
  exam_submission_id: number;
  overall_status: ProcessingOverallStatus;
  is_terminal: boolean;
  can_retry: boolean;
  pending_reason: string | null;
  failure_reason: string | null;
  seal: ProcessingSealStatus;
  capture: ProcessingCaptureStatus;
  grading: ProcessingGradingStatus;
  tasks: ProcessingTaskSummary;
  results: ProcessingResultSummary;
  score: ProcessingScoreSummary;
  timestamps: ProcessingTimestamps;
}

export interface ProcessingStatusApiError {
  code: string;
  message: string;
  details: Record<string, unknown>;
  request_id: string | null;
}

export type ProcessingStatusApiResult =
  | { ok: true; data: ProcessingStatusResponse }
  | { ok: false; status: number; error: ProcessingStatusApiError };
