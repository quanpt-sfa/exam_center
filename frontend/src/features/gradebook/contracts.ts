export type OpenEndedString<T extends string> = T | (string & {});

export type GradebookStatus = OpenEndedString<
  'COMPUTED' | 'NEEDS_REVIEW' | 'PENDING' | 'FAILED' | 'NOT_DISPATCHED'
>;

export interface GradebookApiError {
  code: string;
  message: string;
  details: Record<string, unknown>;
  request_id?: string | null;
  status?: number;
}

export interface GradebookFilters {
  exam_id?: number;
  exam_sitting_id?: number;
  exam_sitting_room_id?: number;
  class_section_id?: number;
  student_query?: string;
  grading_status?: string;
  submission_status?: string;
  needs_review?: boolean;
  limit?: number;
  offset?: number;
}

export interface GradebookRow {
  exam_submission_id: number;
  student_id: number;
  student_code: string | null;
  student_full_name: string | null;
  exam_id: number;
  exam_title: string | null;
  exam_sitting_id: number;
  exam_sitting_room_id: number | null;
  room_name: string | null;
  submission_status: string | null;
  sealed_at: string | null;
  grading_status: GradebookStatus;
  total_score: string | null;
  max_score: string | null;
  percentage: string | null;
  needs_review: boolean;
  question_score_count: number;
  manual_review_count: number;
  last_graded_at: string | null;
}

export interface GradebookListResponse {
  items: GradebookRow[];
  total: number;
  limit: number;
  offset: number;
}

export interface GradebookSubmissionSummary extends GradebookRow {}

export interface GradebookQuestionScore {
  question_score_id: number;
  question_grading_task_id: number;
  exam_submission_id: number;
  submission_seal_id: number;
  generated_exam_question_id: number | null;
  question_order?: number | null;
  question_title?: string | null;
  grading_mode?: string | null;
  raw_score: number | null;
  max_score: number | null;
  normalized_score?: number | null;
  score_percent: number | null;
  score_status: OpenEndedString<'FINALIZED' | 'AUTO_SCORED' | 'MANUAL_OVERRIDE'> | string | null;
  scored_at: string | null;
  requires_manual_review: boolean;
  input_source: string | null;
  answer_language: string | null;
  comparison_method: string | null;
  comparison_status?: string | null;
  scored_engine_code: string | null;
  error_code?: string | null;
  error_message?: string | null;
  feedback?: string | null;
}

export interface GradebookManualReviewSummary {
  manual_review_id: number;
  exam_submission_id: number;
  submission_seal_id: number;
  question_grading_task_id: number | null;
  question_score_id: number | null;
  submission_score_id: number | null;
  review_reason: string | null;
  review_status: OpenEndedString<'OPEN' | 'ASSIGNED' | 'RESOLVED' | 'REJECTED' | 'CANCELLED'> | string | null;
  assigned_to: number | null;
  created_at: string | null;
  resolved_at: string | null;
  resolved_by: number | null;
  note: string | null;
}

export interface GradebookJobSummary {
  grading_job_id: number;
  exam_submission_id: number;
  submission_seal_id: number;
  grading_mode: string;
  grading_status: string;
  attempt_count: number;
  requested_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_code: string | null;
  last_run_no: number | null;
  last_run_status: string | null;
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  needs_review_tasks: number;
  current_submission_score_id: number | null;
  current_total_raw_score: number | null;
  current_total_max_score: number | null;
  current_final_score: number | null;
  current_score_status: string | null;
  current_scored_at: string | null;
}

export interface GradebookEventSummary {
  grading_event_id: number;
  grading_job_id: number | null;
  grading_run_id: number | null;
  question_grading_task_id: number | null;
  event_type: string | null;
  event_at: string | null;
  actor_user_id: number | null;
  worker_id: string | null;
  job_status: string | null;
  run_status: string | null;
  task_status: string | null;
}

export interface GradebookSubmissionScore {
  submission_score_id: number;
  grading_job_id: number;
  exam_submission_id: number;
  submission_seal_id: number;
  score_version_no: number;
  is_current: boolean;
  total_raw_score: number | null;
  total_max_score: number | null;
  final_score: number | null;
  score_status: string | null;
  scored_at: string | null;
  finalized_at: string | null;
}

export interface GradebookSubmissionDetail {
  submission: GradebookSubmissionSummary;
  score: GradebookSubmissionScore | null;
  question_scores: GradebookQuestionScore[];
  manual_reviews: GradebookManualReviewSummary[];
  jobs: GradebookJobSummary[];
  events: GradebookEventSummary[];
}
