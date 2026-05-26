import { render, screen } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';
import { AdminSubjectListPage } from './AdminSubjectListPage';

vi.mock('../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

import { httpRequest } from '../../shared/api/httpClient';

describe('AdminSubjectListPage', () => {
  test('AdminSubjectListPage renders subject rows from mocked API', async () => {
    vi.mocked(httpRequest).mockResolvedValue({
      success: true,
      data: [
        { subject_id: 1, subject_code: 'CS101', subject_name: 'Databases', credits: 3 },
        { subject_id: 2, subject_code: 'CS102', subject_name: 'Algorithms', credits: 4 },
      ],
      message: null,
    });

    render(<AdminSubjectListPage />);

    expect(await screen.findByText('CS101')).toBeInTheDocument();
    expect(screen.getByText('Algorithms')).toBeInTheDocument();
  });
});
