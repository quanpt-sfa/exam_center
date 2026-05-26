import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { httpRequest } from '../../shared/api/httpClient';
import { ChangePasswordPage } from './ChangePasswordPage';

vi.mock('../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

const mockedHttpRequest = vi.mocked(httpRequest);

function renderPage() {
  render(
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ChangePasswordPage />
    </BrowserRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('ChangePasswordPage', () => {
  test('submits current and new password to backend API', async () => {
    mockedHttpRequest.mockResolvedValue({
      ok: true,
      success: true,
      data: { status: 'password_changed' },
      message: null,
      error: null,
    });

    renderPage();

    fireEvent.change(screen.getByLabelText('Mật khẩu hiện tại'), { target: { value: 'old-password' } });
    fireEvent.change(screen.getByLabelText('Mật khẩu mới'), { target: { value: 'new-password-1' } });
    fireEvent.change(screen.getByLabelText('Xác nhận mật khẩu mới'), { target: { value: 'new-password-1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Đổi mật khẩu' }));

    await waitFor(() =>
      expect(mockedHttpRequest).toHaveBeenCalledWith('/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({
          current_password: 'old-password',
          new_password: 'new-password-1',
        }),
      })
    );
    expect(await screen.findByText('Đã đổi mật khẩu thành công.')).toBeInTheDocument();
  });

  test('does not call API when confirmation does not match', async () => {
    renderPage();

    fireEvent.change(screen.getByLabelText('Mật khẩu hiện tại'), { target: { value: 'old-password' } });
    fireEvent.change(screen.getByLabelText('Mật khẩu mới'), { target: { value: 'new-password-1' } });
    fireEvent.change(screen.getByLabelText('Xác nhận mật khẩu mới'), { target: { value: 'new-password-2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Đổi mật khẩu' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Mật khẩu mới và xác nhận mật khẩu không khớp.');
    expect(mockedHttpRequest).not.toHaveBeenCalled();
  });

  test('shows backend error message', async () => {
    mockedHttpRequest.mockResolvedValue({
      ok: false,
      success: false,
      data: null,
      message: null,
      error: {
        code: 'invalid_current_password',
        message: 'Current password is incorrect',
      },
    });

    renderPage();

    fireEvent.change(screen.getByLabelText('Mật khẩu hiện tại'), { target: { value: 'wrong-password' } });
    fireEvent.change(screen.getByLabelText('Mật khẩu mới'), { target: { value: 'new-password-1' } });
    fireEvent.change(screen.getByLabelText('Xác nhận mật khẩu mới'), { target: { value: 'new-password-1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Đổi mật khẩu' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Current password is incorrect');
  });
});
