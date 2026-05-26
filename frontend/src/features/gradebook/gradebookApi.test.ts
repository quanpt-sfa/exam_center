import { beforeEach, describe, expect, test, vi } from 'vitest';
import { httpRequest } from '../../shared/api/httpClient';
import {
  GradebookRequestError,
  getGradebookSubmissionDetail,
  getSubmissionQuestionScores,
  getSubmissionScore,
  listGradebookSubmissions,
  listManualReviews,
} from './gradebookApi';

vi.mock('../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

const mockedHttpRequest = vi.mocked(httpRequest);

const ok = <T,>(data: T) => ({
  ok: true as const,
  success: true as const,
  data,
  message: null,
  error: null,
});

const err = (code: string, message: string, details: Record<string, unknown> = {}) => ({
  ok: false as const,
  success: false as const,
  data: null,
  message: null,
  error: {
    code,
    message,
    details,
    request_id: 'req-gradebook',
  },
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe('gradebook api client', () => {
  test('list endpoint uses expected path and query encoding', async () => {
    mockedHttpRequest.mockResolvedValueOnce(
      ok({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      })
    );

    await listGradebookSubmissions({
      exam_sitting_id: 10,
      student_query: 'SV 001',
      needs_review: false,
      limit: 25,
      offset: 5,
    });

    expect(mockedHttpRequest).toHaveBeenCalledWith(
      '/grading/gradebook?exam_sitting_id=10&student_query=SV+001&needs_review=false&limit=25&offset=5',
      undefined
    );
  });

  test('detail endpoint uses submission detail path', async () => {
    mockedHttpRequest.mockResolvedValueOnce(
      ok({
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
        score: null,
        question_scores: [],
        manual_reviews: [],
        jobs: [],
        events: [],
      })
    );

    await getGradebookSubmissionDetail(123);

    expect(mockedHttpRequest).toHaveBeenCalledWith('/grading/gradebook/submissions/123', undefined);
  });

  test('backend error is preserved for list endpoint', async () => {
    mockedHttpRequest.mockResolvedValueOnce(err('permission_denied', 'Forbidden', { required_roles: ['ADMIN'] }));

    await expect(listGradebookSubmissions()).rejects.toMatchObject({
      name: 'GradebookRequestError',
      code: 'permission_denied',
      message: 'Forbidden',
      details: { required_roles: ['ADMIN'] },
    });
  });

  test('403 permission_denied is preserved', async () => {
    mockedHttpRequest.mockResolvedValueOnce(err('permission_denied', 'Insufficient permissions'));

    await expect(getGradebookSubmissionDetail(10)).rejects.toMatchObject({
      name: 'GradebookRequestError',
      code: 'permission_denied',
      message: 'Insufficient permissions',
    });
  });

  test('404 not found is preserved', async () => {
    mockedHttpRequest.mockResolvedValueOnce(err('submission_not_found', 'Submission not found'));

    await expect(getGradebookSubmissionDetail(999)).rejects.toMatchObject({
      code: 'submission_not_found',
      message: 'Submission not found',
    });
  });

  test('does not fake success on error', async () => {
    mockedHttpRequest.mockResolvedValueOnce(err('network_error', 'Network request failed'));

    await expect(listGradebookSubmissions()).rejects.toBeInstanceOf(GradebookRequestError);
  });

  test('submission score and question score helpers use existing endpoints', async () => {
    mockedHttpRequest
      .mockResolvedValueOnce(ok({ exam_submission_id: 12, status: 'READY', score: null }))
      .mockResolvedValueOnce(ok({ exam_submission_id: 12, items: [] }))
      .mockResolvedValueOnce(ok({ items: [], limit: 100, offset: 0 }));

    await getSubmissionScore(12);
    await getSubmissionQuestionScores(12);
    await listManualReviews();

    expect(mockedHttpRequest).toHaveBeenNthCalledWith(1, '/grading/submissions/12/score', undefined);
    expect(mockedHttpRequest).toHaveBeenNthCalledWith(2, '/grading/submissions/12/question-scores', undefined);
    expect(mockedHttpRequest).toHaveBeenNthCalledWith(3, '/grading/manual-reviews', undefined);
  });
});
