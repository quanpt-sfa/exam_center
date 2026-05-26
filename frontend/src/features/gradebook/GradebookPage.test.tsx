import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { GradebookPage } from './GradebookPage';
import { GradebookRequestError, listGradebookSubmissions } from './gradebookApi';

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
  listGradebookSubmissions: vi.fn(),
}));

const mockedListGradebookSubmissions = vi.mocked(listGradebookSubmissions);

function renderPage(initialEntry = '/grading/gradebook') {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/grading/gradebook" element={<GradebookPage />} />
        <Route path="/grading/gradebook/submissions/:submissionId" element={<div>Detail route placeholder</div>} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('GradebookPage', () => {
  test('renders header and supported filters', async () => {
    mockedListGradebookSubmissions.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    });

    renderPage();

    expect(screen.getByRole('heading', { name: 'Gradebook' })).toBeInTheDocument();
    expect(screen.getByTestId('gradebook-filter-form')).toBeInTheDocument();
    expect(screen.getByLabelText('Exam ID')).toBeInTheDocument();
    expect(screen.getByLabelText('Sitting ID')).toBeInTheDocument();
    expect(screen.getByLabelText('Room ID')).toBeInTheDocument();
    expect(screen.getByLabelText('Student search')).toBeInTheDocument();
    expect(screen.getByLabelText('Grading status')).toBeInTheDocument();
    expect(screen.getByLabelText('Needs review')).toBeInTheDocument();

    await waitFor(() => expect(mockedListGradebookSubmissions).toHaveBeenCalledWith({ limit: 50, offset: 0 }));
  });

  test('shows loading state', () => {
    mockedListGradebookSubmissions.mockReturnValue(new Promise(() => undefined) as never);

    renderPage();

    expect(screen.getByText(/Loading backend gradebook rows/i)).toBeInTheDocument();
  });

  test('shows empty state', async () => {
    mockedListGradebookSubmissions.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    });

    renderPage();

    expect(await screen.findByText(/No submissions match these filters/i)).toBeInTheDocument();
    expect(screen.queryByTestId('gradebook-table')).not.toBeInTheDocument();
  });

  test('shows backend error state', async () => {
    mockedListGradebookSubmissions.mockRejectedValueOnce(
      new GradebookRequestError({
        code: 'permission_denied',
        message: 'Forbidden',
        details: {},
        status: 403,
      })
    );

    renderPage();

    expect(await screen.findByText(/Unable to load the gradebook/i)).toBeInTheDocument();
    expect(screen.getByText('Forbidden')).toBeInTheDocument();
  });

  test('renders computed, needs-review, and pending rows from backend data', async () => {
    mockedListGradebookSubmissions.mockResolvedValueOnce({
      items: [
        {
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
        {
          exam_submission_id: 124,
          student_id: 457,
          student_code: 'SV002',
          student_full_name: 'Tran Thi B',
          exam_id: 1,
          exam_title: 'SQL Midterm',
          exam_sitting_id: 10,
          exam_sitting_room_id: 98,
          room_name: 'Lab A',
          submission_status: 'SUBMITTED',
          sealed_at: '2026-05-20T10:10:00+00:00',
          grading_status: 'NEEDS_REVIEW',
          total_score: '0.00',
          max_score: '10.00',
          percentage: '0.00',
          needs_review: true,
          question_score_count: 1,
          manual_review_count: 1,
          last_graded_at: '2026-05-20T10:11:00+00:00',
        },
        {
          exam_submission_id: 125,
          student_id: 458,
          student_code: 'SV003',
          student_full_name: 'Le Van C',
          exam_id: 1,
          exam_title: 'SQL Midterm',
          exam_sitting_id: 10,
          exam_sitting_room_id: 99,
          room_name: 'Lab B',
          submission_status: 'SEALED',
          sealed_at: null,
          grading_status: 'NOT_DISPATCHED',
          total_score: null,
          max_score: null,
          percentage: null,
          needs_review: false,
          question_score_count: 0,
          manual_review_count: 0,
          last_graded_at: null,
        },
      ],
      total: 3,
      limit: 50,
      offset: 0,
    });

    renderPage();

    expect(await screen.findByText('Nguyen Van A')).toBeInTheDocument();
    expect(screen.getByText('Tran Thi B')).toBeInTheDocument();
    expect(screen.getByText('Le Van C')).toBeInTheDocument();
    expect(screen.getByText('COMPUTED')).toBeInTheDocument();
    expect(screen.getByText('NEEDS_REVIEW')).toBeInTheDocument();
    expect(screen.getByText('NOT_DISPATCHED')).toBeInTheDocument();
    expect(screen.getByText('Computed on this page')).toBeInTheDocument();
    expect(screen.getByText('Pending / not dispatched')).toBeInTheDocument();
  });

  test('clicking detail link navigates to the submission detail route', async () => {
    mockedListGradebookSubmissions.mockResolvedValueOnce({
      items: [
        {
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
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });

    renderPage();

    fireEvent.click(await screen.findByRole('link', { name: /View detail for submission 123/i }));

    expect(await screen.findByText('Detail route placeholder')).toBeInTheDocument();
  });

  test('does not render fake rows on empty response', async () => {
    mockedListGradebookSubmissions.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    });

    renderPage();

    await waitFor(() => expect(mockedListGradebookSubmissions).toHaveBeenCalled());
    expect(screen.queryByText('Nguyen Van A')).not.toBeInTheDocument();
  });
});
