import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { GradebookSubmissionDetailPage } from './GradebookSubmissionDetailPage';
import { GradebookRequestError, getGradebookSubmissionDetail } from './gradebookApi';

vi.mock('./gradebookApi', () => ({
  GradebookRequestError: class GradebookRequestError extends Error {
    code: string;
    details: Record<string, unknown>;
    request_id: string | null;
    status: number;
    constructor(payload: { code: string; message: string; details?: Record<string, unknown>; request_id?: string | null; status?: number }) {
      super(payload.message);
      this.name = 'GradebookRequestError';
      this.code = payload.code;
      this.details = payload.details ?? {};
      this.request_id = payload.request_id ?? null;
      this.status = payload.status ?? 0;
    }
  },
  getGradebookSubmissionDetail: vi.fn(),
}));

const mockedGetGradebookSubmissionDetail = vi.mocked(getGradebookSubmissionDetail);

function renderPage(path = '/grading/gradebook/submissions/123') {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={[path]}>
      <Routes>
        <Route path="/grading/gradebook/submissions/:submissionId" element={<GradebookSubmissionDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('GradebookSubmissionDetailPage', () => {
  test('shows loading state', () => {
    mockedGetGradebookSubmissionDetail.mockReturnValue(new Promise(() => undefined) as never);

    renderPage();

    expect(screen.getByText(/Loading backend result review detail/i)).toBeInTheDocument();
  });

  test('shows error state', async () => {
    mockedGetGradebookSubmissionDetail.mockRejectedValueOnce(
      new GradebookRequestError({
        code: 'submission_not_found',
        message: 'Submission not found',
        details: {},
        status: 404,
      })
    );

    renderPage();

    expect(await screen.findByRole('heading', { name: 'Submission not found' })).toBeInTheDocument();
    expect(screen.getAllByText('Submission not found')).toHaveLength(2);
  });

  test('renders submission summary, score summary, and question score rows', async () => {
    mockedGetGradebookSubmissionDetail.mockResolvedValueOnce({
      submission: {
        exam_submission_id: 123,
        student_id: 456,
        student_code: 'SV001',
        student_full_name: 'Nguyen Van A',
        exam_id: 1,
        exam_title: 'SQL Midterm',
        exam_sitting_id: 10,
        exam_sitting_room_id: 98,
        room_name: 'Lab A',
        submission_status: 'SUBMITTED',
        sealed_at: '2026-05-20T10:00:00+00:00',
        grading_status: 'COMPUTED',
        total_score: '10.00',
        max_score: '10.00',
        percentage: '100.00',
        needs_review: false,
        question_score_count: 1,
        manual_review_count: 0,
        last_graded_at: '2026-05-20T10:05:00+00:00',
      },
      score: {
        submission_score_id: 1,
        grading_job_id: 2,
        exam_submission_id: 123,
        submission_seal_id: 9001,
        score_version_no: 1,
        is_current: true,
        total_raw_score: 10,
        total_max_score: 10,
        final_score: 10,
        score_status: 'FINALIZED',
        scored_at: '2026-05-20T10:05:00+00:00',
        finalized_at: '2026-05-20T10:06:00+00:00',
      },
      question_scores: [
        {
          question_score_id: 7,
          question_grading_task_id: 8,
          exam_submission_id: 123,
          submission_seal_id: 9001,
          generated_exam_question_id: 501,
          question_order: 1,
          question_title: 'Question 1',
          grading_mode: 'SQL_TEXTBOX',
          raw_score: 10,
          max_score: 10,
          normalized_score: 1,
          score_percent: 100,
          score_status: 'AUTO_SCORED',
          scored_at: '2026-05-20T10:05:00+00:00',
          requires_manual_review: false,
          input_source: 'SEALED_TEXT_ANSWER',
          answer_language: 'SQL',
          comparison_method: 'RESULT_SET',
          comparison_status: 'MATCHED',
          scored_engine_code: 'SQL_TEXTBOX',
          error_code: null,
          error_message: null,
          feedback: 'Matched expected result set.',
        },
      ],
      manual_reviews: [],
      jobs: [],
      events: [],
    });

    renderPage();

    expect(await screen.findByText('Nguyen Van A')).toBeInTheDocument();
    expect(screen.getByText('Score summary')).toBeInTheDocument();
    expect(screen.getByText('Question scores')).toBeInTheDocument();
    expect(screen.getByTestId('gradebook-question-scores-table')).toBeInTheDocument();
    expect(screen.getByText('Question 1')).toBeInTheDocument();
    expect(screen.getByText('AUTO_SCORED')).toBeInTheDocument();
    expect(screen.getByText('Matched expected result set.')).toBeInTheDocument();
  });

  test('renders needs-review and backend error details', async () => {
    mockedGetGradebookSubmissionDetail.mockResolvedValueOnce({
      submission: {
        exam_submission_id: 123,
        student_id: 456,
        student_code: 'SV001',
        student_full_name: 'Tran Thi B',
        exam_id: 1,
        exam_title: 'SQL Midterm',
        exam_sitting_id: 10,
        exam_sitting_room_id: 98,
        room_name: 'Lab A',
        submission_status: 'SUBMITTED',
        sealed_at: '2026-05-20T10:00:00+00:00',
        grading_status: 'NEEDS_REVIEW',
        total_score: '0.00',
        max_score: '10.00',
        percentage: '0.00',
        needs_review: true,
        question_score_count: 1,
        manual_review_count: 1,
        last_graded_at: '2026-05-20T10:05:00+00:00',
      },
      score: {
        submission_score_id: 1,
        grading_job_id: 2,
        exam_submission_id: 123,
        submission_seal_id: 9001,
        score_version_no: 1,
        is_current: true,
        total_raw_score: 0,
        total_max_score: 10,
        final_score: 0,
        score_status: 'NEEDS_REVIEW',
        scored_at: '2026-05-20T10:05:00+00:00',
        finalized_at: null,
      },
      question_scores: [
        {
          question_score_id: 7,
          question_grading_task_id: 8,
          exam_submission_id: 123,
          submission_seal_id: 9001,
          generated_exam_question_id: 501,
          question_order: 1,
          question_title: 'Question 1',
          grading_mode: 'SQL_TEXTBOX',
          raw_score: 0,
          max_score: 10,
          normalized_score: null,
          score_percent: 0,
          score_status: 'NEEDS_REVIEW',
          scored_at: '2026-05-20T10:05:00+00:00',
          requires_manual_review: true,
          input_source: 'SEALED_TEXT_ANSWER',
          answer_language: 'SQL',
          comparison_method: 'RESULT_SET',
          comparison_status: 'POLICY_VIOLATION',
          scored_engine_code: 'SQL_TEXTBOX',
          error_code: 'SQL_POLICY_BLOCK',
          error_message: 'Policy violation detected.',
          feedback: null,
        },
      ],
      manual_reviews: [
        {
          manual_review_id: 5,
          exam_submission_id: 123,
          submission_seal_id: 9001,
          question_grading_task_id: 8,
          question_score_id: 7,
          submission_score_id: 1,
          review_reason: 'Policy violation',
          review_status: 'OPEN',
          assigned_to: null,
          created_at: '2026-05-20T10:06:00+00:00',
          resolved_at: null,
          resolved_by: null,
          note: 'Needs instructor review',
        },
      ],
      jobs: [
        {
          grading_job_id: 10,
          exam_submission_id: 123,
          submission_seal_id: 9001,
          grading_mode: 'SQL_TEXTBOX',
          grading_status: 'NEEDS_REVIEW',
          attempt_count: 1,
          requested_at: '2026-05-20T10:04:00+00:00',
          started_at: '2026-05-20T10:05:00+00:00',
          finished_at: '2026-05-20T10:06:00+00:00',
          error_code: 'SQL_POLICY_BLOCK',
          last_run_no: 1,
          last_run_status: 'NEEDS_REVIEW',
          total_tasks: 1,
          completed_tasks: 0,
          failed_tasks: 0,
          needs_review_tasks: 1,
          current_submission_score_id: 1,
          current_total_raw_score: 0,
          current_total_max_score: 10,
          current_final_score: 0,
          current_score_status: 'NEEDS_REVIEW',
          current_scored_at: '2026-05-20T10:05:00+00:00',
        },
      ],
      events: [
        {
          grading_event_id: 11,
          grading_job_id: 10,
          grading_run_id: 12,
          question_grading_task_id: 8,
          event_type: 'QUESTION_REQUIRES_REVIEW',
          event_at: '2026-05-20T10:06:00+00:00',
          actor_user_id: null,
          worker_id: 'worker-1',
          job_status: 'NEEDS_REVIEW',
          run_status: 'NEEDS_REVIEW',
          task_status: 'NEEDS_REVIEW',
        },
      ],
    });

    renderPage();

    expect(await screen.findByRole('heading', { name: 'Needs review' })).toBeInTheDocument();
    expect(screen.getByText('Policy violation detected.')).toBeInTheDocument();
    expect(screen.getAllByText('SQL_POLICY_BLOCK')).toHaveLength(2);
    expect(screen.getByText('OPEN')).toBeInTheDocument();
    expect(screen.getByText(/QUESTION_REQUIRES_REVIEW at/i)).toBeInTheDocument();
  });

  test('unknown status renders safely and no score adjustment or answer preview controls are shown', async () => {
    mockedGetGradebookSubmissionDetail.mockResolvedValueOnce({
      submission: {
        exam_submission_id: 123,
        student_id: 456,
        student_code: 'SV001',
        student_full_name: 'Nguyen Van A',
        exam_id: 1,
        exam_title: 'SQL Midterm',
        exam_sitting_id: 10,
        exam_sitting_room_id: 98,
        room_name: 'Lab A',
        submission_status: 'SUBMITTED',
        sealed_at: '2026-05-20T10:00:00+00:00',
        grading_status: 'WEIRD_UNKNOWN_STATUS',
        total_score: null,
        max_score: null,
        percentage: null,
        needs_review: false,
        question_score_count: 0,
        manual_review_count: 0,
        last_graded_at: null,
      },
      score: null,
      question_scores: [],
      manual_reviews: [],
      jobs: [],
      events: [],
    });

    renderPage();

    expect(await screen.findByText('WEIRD_UNKNOWN_STATUS')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /adjust score/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/preview file/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /download uploaded file/i })).not.toBeInTheDocument();
  });
});
