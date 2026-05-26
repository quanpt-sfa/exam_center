import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { httpRequest } from '../../shared/api/httpClient';
import { AccountAdminPage } from './AccountAdminPage';

vi.mock('../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

const mockedHttpRequest = vi.mocked(httpRequest);

function okEnvelope<T>(data: T) {
  return {
    ok: true,
    success: true,
    data,
    message: null,
    error: null,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(window, 'confirm').mockReturnValue(true);
});

describe('AccountAdminPage', () => {
  test('loads user accounts without rendering secrets', async () => {
    mockedHttpRequest.mockResolvedValueOnce(
      okEnvelope({
        items: [
          {
            user_id: 10,
            username: 'student001',
            email_login: 'student001@example.test',
            display_name: 'Student One',
            user_status: 'ACTIVE',
            roles: ['STUDENT'],
            password_hash: 'must-not-render',
          },
        ],
      })
    );

    render(<AccountAdminPage />);

    expect(await screen.findByText('student001')).toBeInTheDocument();
    expect(screen.getByText('Student One')).toBeInTheDocument();
    expect(screen.queryByText('must-not-render')).not.toBeInTheDocument();
    expect(mockedHttpRequest).toHaveBeenCalledWith('/identity/users?page=1&page_size=50');
  });

  test('resets password to username through backend API', async () => {
    mockedHttpRequest
      .mockResolvedValueOnce(
        okEnvelope({
          items: [
            {
              user_id: 10,
              username: 'student001',
              email_login: null,
              display_name: 'Student One',
              user_status: 'ACTIVE',
              roles: ['STUDENT'],
            },
          ],
        })
      )
      .mockResolvedValueOnce(
        okEnvelope({
          user_id: 10,
          username: 'student001',
          password_reset: true,
          reset_policy: 'USERNAME',
        })
      )
      .mockResolvedValueOnce(
        okEnvelope({
          items: [
            {
              user_id: 10,
              username: 'student001',
              email_login: null,
              display_name: 'Student One',
              user_status: 'ACTIVE',
              roles: ['STUDENT'],
            },
          ],
        })
      );

    render(<AccountAdminPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Reset password' }));

    await waitFor(() =>
      expect(mockedHttpRequest).toHaveBeenCalledWith('/identity/users/10/reset-password-to-username', {
        method: 'POST',
      })
    );
    expect(await screen.findByText(/Da reset password cho student001/i)).toBeInTheDocument();
  });
});
