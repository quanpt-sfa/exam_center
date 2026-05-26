import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, expect, test, vi } from 'vitest';
import { ExamListPage } from './ExamListPage';

vi.mock('../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

import { httpRequest } from '../../shared/api/httpClient';

describe('ExamListPage', () => {
  test('ExamListPage highlights the actionable exam and keeps a link back to dashboard', async () => {
    vi.mocked(httpRequest).mockResolvedValue({
      ok: true,
      success: true,
      data: {
        items: [
          { exam_session_id: 10, sitting_name: 'Midterm SQL', course_name: 'Databases', session_status: 'IN_PROGRESS' },
          { exam_session_id: 11, sitting_name: 'Final SQL', course_name: 'Databases', session_status: 'COMPLETED', exam_submission_id: 501, submission_status: 'SUBMITTED' },
        ],
      },
      message: null,
      error: null,
    });

    render(
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ExamListPage />
      </BrowserRouter>
    );

    expect(await screen.findByRole('link', { name: /Quay lại dashboard/i })).toHaveAttribute('href', '/dashboard');
    expect(await screen.findByRole('link', { name: /Đi tới ca đang mở/i })).toHaveAttribute('href', '/exams/10');
    expect(screen.getByText('Ca thi cần vào ngay')).toBeInTheDocument();
    expect(screen.getByText('Midterm SQL')).toBeInTheDocument();
    expect(screen.getByText('Final SQL')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Tiếp tục làm bài/i })).toHaveAttribute('href', '/exams/10');
    expect(screen.getByRole('link', { name: /Xem kết quả/i })).toHaveAttribute('href', '/submissions/501/result');
  });

  test('ExamListPage still renders all assigned exams when none is currently actionable', async () => {
    vi.mocked(httpRequest).mockResolvedValue({
      ok: true,
      success: true,
      data: {
        items: [
          { exam_session_id: 12, sitting_name: 'Quiz SQL', course_name: 'Databases', session_status: 'COMPLETED', exam_submission_id: 502, submission_status: 'GRADED' },
        ],
      },
      message: null,
      error: null,
    });

    render(
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ExamListPage />
      </BrowserRouter>
    );

    expect(await screen.findByText('Tất cả ca thi được phân công')).toBeInTheDocument();
    expect(screen.queryByText('Ca thi cần vào ngay')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Xem kết quả/i })).toHaveAttribute('href', '/submissions/502/result');
  });
});
