import { httpRequest } from '../../shared/api/httpClient';
import type {
  GradebookApiError,
  GradebookEventSummary,
  GradebookFilters,
  GradebookJobSummary,
  GradebookListResponse,
  GradebookManualReviewSummary,
  GradebookQuestionScore,
  GradebookRow,
  GradebookSubmissionDetail,
  GradebookSubmissionScore,
  GradebookSubmissionSummary,
} from './contracts';

export class GradebookRequestError extends Error {
  code: string;
  details: Record<string, unknown>;
  request_id: string | null;
  status: number;

  constructor(payload: GradebookApiError) {
    super(payload.message);
    this.name = 'GradebookRequestError';
    this.code = payload.code;
    this.details = payload.details;
    this.request_id = payload.request_id ?? null;
    this.status = payload.status ?? 0;
  }
}

type LegacyApiResult<T> = Awaited<ReturnType<typeof httpRequest<T>>>;

function mapApiError<T>(response: LegacyApiResult<T>): GradebookApiError {
  if (response.ok) {
    return {
      code: 'invalid_response',
      message: 'Unexpected API success state',
      details: {},
      request_id: null,
      status: 502,
    };
  }

  const inferredStatus =
    response.error.code === 'permission_denied'
      ? 403
      : response.error.code === 'submission_not_found'
        ? 404
        : response.error.code === 'validation_error'
          ? 422
          : response.error.code === 'network_error'
            ? 0
            : 0;

  return {
    code: response.error.code,
    message: response.error.message,
    details: response.error.details,
    request_id: response.error.request_id ?? null,
    status: inferredStatus,
  };
}

async function requestData<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await httpRequest<T>(path, init);
  if (!response.ok) {
    throw new GradebookRequestError(mapApiError(response));
  }
  return response.data;
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};
}

function asNumber(value: unknown): number {
  return Number(value);
}

function asNullableNumber(value: unknown): number | null {
  return value == null ? null : Number(value);
}

function asString(value: unknown): string {
  return String(value ?? '');
}

function asNullableString(value: unknown): string | null {
  return value == null ? null : String(value);
}

function normalizeGradebookRow(value: unknown): GradebookRow {
  const row = asRecord(value);
  return {
    exam_submission_id: asNumber(row.exam_submission_id),
    student_id: asNumber(row.student_id),
    student_code: asNullableString(row.student_code),
    student_full_name: asNullableString(row.student_full_name),
    exam_id: asNumber(row.exam_id),
    exam_title: asNullableString(row.exam_title),
    exam_sitting_id: asNumber(row.exam_sitting_id),
    exam_sitting_room_id: asNullableNumber(row.exam_sitting_room_id),
    room_name: asNullableString(row.room_name),
    submission_status: asNullableString(row.submission_status),
    sealed_at: asNullableString(row.sealed_at),
    grading_status: asString(row.grading_status),
    total_score: asNullableString(row.total_score),
    max_score: asNullableString(row.max_score),
    percentage: asNullableString(row.percentage),
    needs_review: Boolean(row.needs_review),
    question_score_count: asNumber(row.question_score_count ?? 0),
    manual_review_count: asNumber(row.manual_review_count ?? 0),
    last_graded_at: asNullableString(row.last_graded_at),
  };
}

function normalizeSubmissionScore(value: unknown): GradebookSubmissionScore {
  const row = asRecord(value);
  return {
    submission_score_id: asNumber(row.submission_score_id),
    grading_job_id: asNumber(row.grading_job_id),
    exam_submission_id: asNumber(row.exam_submission_id),
    submission_seal_id: asNumber(row.submission_seal_id),
    score_version_no: asNumber(row.score_version_no),
    is_current: Boolean(row.is_current),
    total_raw_score: asNullableNumber(row.total_raw_score),
    total_max_score: asNullableNumber(row.total_max_score),
    final_score: asNullableNumber(row.final_score),
    score_status: asNullableString(row.score_status),
    scored_at: asNullableString(row.scored_at),
    finalized_at: asNullableString(row.finalized_at),
  };
}

function normalizeQuestionScore(value: unknown): GradebookQuestionScore {
  const row = asRecord(value);
  return {
    question_score_id: asNumber(row.question_score_id),
    question_grading_task_id: asNumber(row.question_grading_task_id),
    exam_submission_id: asNumber(row.exam_submission_id),
    submission_seal_id: asNumber(row.submission_seal_id),
    generated_exam_question_id: asNullableNumber(row.generated_exam_question_id),
    question_order: asNullableNumber(row.question_order),
    question_title: asNullableString(row.question_title),
    grading_mode: asNullableString(row.grading_mode),
    raw_score: asNullableNumber(row.raw_score),
    max_score: asNullableNumber(row.max_score),
    normalized_score: asNullableNumber(row.normalized_score),
    score_percent: asNullableNumber(row.score_percent),
    score_status: asNullableString(row.score_status),
    scored_at: asNullableString(row.scored_at),
    requires_manual_review: Boolean(row.requires_manual_review),
    input_source: asNullableString(row.input_source),
    answer_language: asNullableString(row.answer_language),
    comparison_method: asNullableString(row.comparison_method),
    comparison_status: asNullableString(row.comparison_status),
    scored_engine_code: asNullableString(row.scored_engine_code),
    error_code: asNullableString(row.error_code),
    error_message: asNullableString(row.error_message),
    feedback: asNullableString(row.feedback),
  };
}

function normalizeManualReview(value: unknown): GradebookManualReviewSummary {
  const row = asRecord(value);
  return {
    manual_review_id: asNumber(row.manual_review_id),
    exam_submission_id: asNumber(row.exam_submission_id),
    submission_seal_id: asNumber(row.submission_seal_id),
    question_grading_task_id: asNullableNumber(row.question_grading_task_id),
    question_score_id: asNullableNumber(row.question_score_id),
    submission_score_id: asNullableNumber(row.submission_score_id),
    review_reason: asNullableString(row.review_reason),
    review_status: asNullableString(row.review_status),
    assigned_to: asNullableNumber(row.assigned_to),
    created_at: asNullableString(row.created_at),
    resolved_at: asNullableString(row.resolved_at),
    resolved_by: asNullableNumber(row.resolved_by),
    note: asNullableString(row.note),
  };
}

function normalizeJob(value: unknown): GradebookJobSummary {
  const row = asRecord(value);
  return {
    grading_job_id: asNumber(row.grading_job_id),
    exam_submission_id: asNumber(row.exam_submission_id),
    submission_seal_id: asNumber(row.submission_seal_id),
    grading_mode: asString(row.grading_mode),
    grading_status: asString(row.grading_status),
    attempt_count: asNumber(row.attempt_count ?? 0),
    requested_at: asNullableString(row.requested_at),
    started_at: asNullableString(row.started_at),
    finished_at: asNullableString(row.finished_at),
    error_code: asNullableString(row.error_code),
    last_run_no: asNullableNumber(row.last_run_no),
    last_run_status: asNullableString(row.last_run_status),
    total_tasks: asNumber(row.total_tasks ?? 0),
    completed_tasks: asNumber(row.completed_tasks ?? 0),
    failed_tasks: asNumber(row.failed_tasks ?? 0),
    needs_review_tasks: asNumber(row.needs_review_tasks ?? 0),
    current_submission_score_id: asNullableNumber(row.current_submission_score_id),
    current_total_raw_score: asNullableNumber(row.current_total_raw_score),
    current_total_max_score: asNullableNumber(row.current_total_max_score),
    current_final_score: asNullableNumber(row.current_final_score),
    current_score_status: asNullableString(row.current_score_status),
    current_scored_at: asNullableString(row.current_scored_at),
  };
}

function normalizeEvent(value: unknown): GradebookEventSummary {
  const row = asRecord(value);
  return {
    grading_event_id: asNumber(row.grading_event_id),
    grading_job_id: asNullableNumber(row.grading_job_id),
    grading_run_id: asNullableNumber(row.grading_run_id),
    question_grading_task_id: asNullableNumber(row.question_grading_task_id),
    event_type: asNullableString(row.event_type),
    event_at: asNullableString(row.event_at),
    actor_user_id: asNullableNumber(row.actor_user_id),
    worker_id: asNullableString(row.worker_id),
    job_status: asNullableString(row.job_status),
    run_status: asNullableString(row.run_status),
    task_status: asNullableString(row.task_status),
  };
}

function normalizeListResponse(value: unknown): GradebookListResponse {
  const row = asRecord(value);
  const items = Array.isArray(row.items) ? row.items.map(normalizeGradebookRow) : [];
  return {
    items,
    total: asNumber(row.total ?? 0),
    limit: asNumber(row.limit ?? items.length),
    offset: asNumber(row.offset ?? 0),
  };
}

function normalizeDetailResponse(value: unknown): GradebookSubmissionDetail {
  const row = asRecord(value);
  const submission = normalizeGradebookRow(row.submission);
  const score = row.score == null ? null : normalizeSubmissionScore(row.score);
  const questionScores = Array.isArray(row.question_scores) ? row.question_scores.map(normalizeQuestionScore) : [];
  const manualReviews = Array.isArray(row.manual_reviews) ? row.manual_reviews.map(normalizeManualReview) : [];
  const jobs = Array.isArray(row.jobs) ? row.jobs.map(normalizeJob) : [];
  const events = Array.isArray(row.events) ? row.events.map(normalizeEvent) : [];

  return {
    submission: submission as GradebookSubmissionSummary,
    score,
    question_scores: questionScores,
    manual_reviews: manualReviews,
    jobs,
    events,
  };
}

function buildListQuery(filters: GradebookFilters = {}): string {
  const params = new URLSearchParams();
  if (filters.exam_id !== undefined) params.set('exam_id', String(filters.exam_id));
  if (filters.exam_sitting_id !== undefined) params.set('exam_sitting_id', String(filters.exam_sitting_id));
  if (filters.exam_sitting_room_id !== undefined) params.set('exam_sitting_room_id', String(filters.exam_sitting_room_id));
  if (filters.class_section_id !== undefined) params.set('class_section_id', String(filters.class_section_id));
  if (filters.student_query) params.set('student_query', filters.student_query);
  if (filters.grading_status) params.set('grading_status', filters.grading_status);
  if (filters.submission_status) params.set('submission_status', filters.submission_status);
  if (filters.needs_review !== undefined) params.set('needs_review', String(filters.needs_review));
  if (filters.limit !== undefined) params.set('limit', String(filters.limit));
  if (filters.offset !== undefined) params.set('offset', String(filters.offset));
  const query = params.toString();
  return query ? `/grading/gradebook?${query}` : '/grading/gradebook';
}

export async function listGradebookSubmissions(filters: GradebookFilters = {}): Promise<GradebookListResponse> {
  const data = await requestData<unknown>(buildListQuery(filters));
  return normalizeListResponse(data);
}

export async function getGradebookSubmissionDetail(submissionId: number): Promise<GradebookSubmissionDetail> {
  const data = await requestData<unknown>(`/grading/gradebook/submissions/${submissionId}`);
  return normalizeDetailResponse(data);
}

export async function getSubmissionScore(submissionId: number): Promise<{
  exam_submission_id: number;
  status: string;
  score: GradebookSubmissionScore | null;
}> {
  const data = await requestData<unknown>(`/grading/submissions/${submissionId}/score`);
  const row = asRecord(data);
  return {
    exam_submission_id: asNumber(row.exam_submission_id),
    status: asString(row.status),
    score: row.score == null ? null : normalizeSubmissionScore(row.score),
  };
}

export async function getSubmissionQuestionScores(submissionId: number): Promise<{
  exam_submission_id: number;
  items: GradebookQuestionScore[];
}> {
  const data = await requestData<unknown>(`/grading/submissions/${submissionId}/question-scores`);
  const row = asRecord(data);
  return {
    exam_submission_id: asNumber(row.exam_submission_id),
    items: Array.isArray(row.items) ? row.items.map(normalizeQuestionScore) : [],
  };
}

export async function listManualReviews(filters?: {
  review_status?: string;
  limit?: number;
  offset?: number;
}): Promise<{ items: GradebookManualReviewSummary[]; limit: number; offset: number }> {
  const params = new URLSearchParams();
  if (filters?.review_status) params.set('review_status', filters.review_status);
  if (filters?.limit !== undefined) params.set('limit', String(filters.limit));
  if (filters?.offset !== undefined) params.set('offset', String(filters.offset));
  const query = params.toString();
  const path = query ? `/grading/manual-reviews?${query}` : '/grading/manual-reviews';
  const data = await requestData<unknown>(path);
  const row = asRecord(data);
  return {
    items: Array.isArray(row.items) ? row.items.map(normalizeManualReview) : [],
    limit: asNumber(row.limit ?? 0),
    offset: asNumber(row.offset ?? 0),
  };
}
