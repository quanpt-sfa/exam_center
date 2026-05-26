import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { httpRequest } from '../../shared/api/httpClient';
import {
  clearAuthTokens,
  getAccessToken,
  getRefreshToken,
  setAccessToken,
  setRefreshToken,
} from '../../shared/auth/tokenStorage';
import { usePublicSettings } from '../settings/usePublicSettings';
import { LoginPage } from './LoginPage';

const navigateMock = vi.fn();

vi.mock('../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

vi.mock('../../shared/auth/tokenStorage', () => ({
  clearAuthTokens: vi.fn(),
  getAccessToken: vi.fn(),
  getRefreshToken: vi.fn(),
  setAccessToken: vi.fn(),
  setRefreshToken: vi.fn(),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock('../settings/usePublicSettings', () => ({
  usePublicSettings: vi.fn(),
}));

const mockedHttpRequest = vi.mocked(httpRequest);
const mockedClearAuthTokens = vi.mocked(clearAuthTokens);
const mockedGetAccessToken = vi.mocked(getAccessToken);
const mockedGetRefreshToken = vi.mocked(getRefreshToken);
const mockedSetAccessToken = vi.mocked(setAccessToken);
const mockedSetRefreshToken = vi.mocked(setRefreshToken);
const mockedUsePublicSettings = vi.mocked(usePublicSettings);

function renderLoginPage() {
  render(
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <LoginPage />
    </BrowserRouter>
  );
}

function fillAndSubmitLoginForm(username: string, password: string) {
  fireEvent.change(screen.getByLabelText(/tài khoản hoặc email/i), { target: { value: username } });
  fireEvent.change(screen.getByLabelText(/^mật khẩu$/i, { selector: 'input' }), { target: { value: password } });
  fireEvent.click(screen.getByRole('button', { name: /^đăng nhập$/i }));
}

beforeEach(() => {
  vi.clearAllMocks();
  mockedGetAccessToken.mockReturnValue(null);
  mockedGetRefreshToken.mockReturnValue(null);

  mockedUsePublicSettings.mockReturnValue({
    settings: {
      academy_name: 'Học viện Công nghệ Bưu chính Viễn thông',
      portal_logo_url: 'https://assets.local/logo.png',
      exam_regulations: 'Rules',
      support_email: 'support@academy.edu.vn',
      support_hotline: '0123-456-789',
    },
    loading: false,
    error: null,
  });
});

describe('LoginPage', () => {
  test('LoginPage renders username/password fields', () => {
    renderLoginPage();

    screen.getByLabelText(/tài khoản hoặc email/i);
    screen.getByLabelText(/^mật khẩu$/i, { selector: 'input' });
  });

  test('posts identifier instead of login', async () => {
    mockedHttpRequest.mockResolvedValue({
      ok: false,
      success: false,
      data: null,
      message: null,
      error: {
        code: 'invalid_credentials',
        message: 'Invalid credentials',
      },
    });

    renderLoginPage();
    fillAndSubmitLoginForm('ue2e_student_owner', '123');

    await waitFor(() => expect(mockedHttpRequest).toHaveBeenCalledTimes(1));
    const [, requestInit] = mockedHttpRequest.mock.calls[0];
    const parsedBody = JSON.parse(String(requestInit?.body ?? '{}')) as Record<string, unknown>;

    expect(parsedBody.identifier).toBe('ue2e_student_owner');
    expect(parsedBody.password).toBe('123');
    expect(parsedBody.login).toBeUndefined();
  });

  test('successful admin login stores access token and navigates to dashboard route', async () => {
    mockedHttpRequest.mockResolvedValue({
      ok: true,
      success: true,
      data: {
        access_token: 'admin-access-token',
        refresh_token: 'admin-refresh-token',
        user: {
          user_id: 1,
          username: 'admin',
          roles: ['ADMIN'],
        },
      },
      message: null,
      error: null,
    });

    renderLoginPage();
    fillAndSubmitLoginForm('admin', '123');

    await waitFor(() => expect(mockedSetAccessToken).toHaveBeenCalledWith('admin-access-token'));
    expect(mockedSetRefreshToken).toHaveBeenCalledWith('admin-refresh-token');
    expect(navigateMock).toHaveBeenCalledWith('/dashboard');
  });

  test('successful student login stores access token and navigates to dashboard route', async () => {
    mockedHttpRequest.mockResolvedValue({
      ok: true,
      success: true,
      data: {
        access_token: 'student-access-token',
        refresh_token: 'student-refresh-token',
        user: {
          user_id: 2,
          username: 'student',
          roles: ['STUDENT'],
        },
      },
      message: null,
      error: null,
    });

    renderLoginPage();
    fillAndSubmitLoginForm('ue2e_student_owner', '123');

    await waitFor(() => expect(mockedSetAccessToken).toHaveBeenCalledWith('student-access-token'));
    expect(mockedSetRefreshToken).toHaveBeenCalledWith('student-refresh-token');
    expect(navigateMock).toHaveBeenCalledWith('/dashboard');
  });

  test('LoginPage with access token redirects to dashboard', async () => {
    mockedGetAccessToken.mockReturnValue('existing-access-token');

    renderLoginPage();

    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/dashboard', { replace: true }));
    expect(mockedHttpRequest).not.toHaveBeenCalled();
  });

  test('LoginPage with refresh token and successful restore redirects to dashboard', async () => {
    mockedGetRefreshToken.mockReturnValue('valid-refresh-token');
    mockedHttpRequest.mockResolvedValueOnce({
      ok: true,
      success: true,
      data: {
        user_id: 2,
        username: 'student',
        display_name: 'Student',
        roles: ['STUDENT'],
        permissions: [],
        active: true,
      },
      message: null,
      error: null,
    });

    renderLoginPage();

    expect(screen.getByRole('status')).toHaveTextContent('Đang khôi phục phiên đăng nhập...');
    expect(screen.queryByRole('button', { name: /^đăng nhập$/i })).not.toBeInTheDocument();
    await waitFor(() => expect(mockedHttpRequest).toHaveBeenCalledWith('/auth/me'));
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/dashboard', { replace: true }));
    expect(mockedClearAuthTokens).not.toHaveBeenCalled();
  });

  test('LoginPage with refresh token and failed restore clears tokens and shows login form', async () => {
    mockedGetRefreshToken.mockReturnValue('stale-refresh-token');
    mockedHttpRequest.mockResolvedValueOnce({
      ok: false,
      success: false,
      data: null,
      message: null,
      error: {
        code: 'invalid_token',
        message: 'Invalid or expired token',
      },
    });

    renderLoginPage();

    expect(screen.getByRole('status')).toHaveTextContent('Đang khôi phục phiên đăng nhập...');
    expect(await screen.findByRole('alert')).toHaveTextContent('Phiên đăng nhập trước không còn hiệu lực. Vui lòng đăng nhập lại.');
    expect(mockedClearAuthTokens).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: /^đăng nhập$/i })).toBeInTheDocument();
  });

  test('during restore login submit is not available', () => {
    mockedGetRefreshToken.mockReturnValue('refresh-token');
    mockedHttpRequest.mockImplementation(() => new Promise(() => undefined));

    renderLoginPage();

    expect(screen.getByRole('status')).toHaveTextContent('Đang khôi phục phiên đăng nhập...');
    expect(screen.queryByRole('button', { name: /^đăng nhập$/i })).not.toBeInTheDocument();
  });

  test('renders error message from error envelope', async () => {
    mockedHttpRequest.mockResolvedValue({
      ok: false,
      success: false,
      data: null,
      message: null,
      error: {
        code: 'invalid_credentials',
        message: 'Wrong username or password.',
      },
    });

    renderLoginPage();
    fillAndSubmitLoginForm('invalid', 'invalid');

    await screen.findByText('Thông tin đăng nhập chưa đúng. Vui lòng nhập lại mật khẩu.');
    expect(mockedSetAccessToken).not.toHaveBeenCalled();
  });

  test('failed login clears the password field, keeps identifier, hides password, and focuses password input', async () => {
    mockedHttpRequest.mockResolvedValue({
      ok: false,
      success: false,
      data: null,
      message: null,
      error: {
        code: 'invalid_credentials',
        message: 'Invalid username/email or password',
      },
    });

    renderLoginPage();

    const identifierInput = screen.getByLabelText(/tài khoản hoặc email/i);
    const passwordInput = screen.getByLabelText(/^mật khẩu$/i, { selector: 'input' });
    fireEvent.change(identifierInput, { target: { value: 'ue2e_student_owner' } });
    fireEvent.change(passwordInput, { target: { value: 'wrong-password' } });
    fireEvent.click(screen.getByRole('button', { name: /hiện mật khẩu/i }));

    expect(passwordInput).toHaveAttribute('type', 'text');

    fireEvent.click(screen.getByRole('button', { name: /^đăng nhập$/i }));

    await screen.findByRole('alert');
    expect(identifierInput).toHaveValue('ue2e_student_owner');
    expect(passwordInput).toHaveValue('');
    expect(passwordInput).toHaveAttribute('type', 'password');
    await waitFor(() => expect(passwordInput).toHaveFocus());
  });

  test('renders validation error message from validation error envelope', async () => {
    mockedHttpRequest.mockResolvedValue({
      ok: false,
      success: false,
      data: null,
      message: null,
      error: {
        code: 'validation_error',
        message: 'Request validation failed',
        details: {
          field: 'identifier',
        },
      },
    });

    renderLoginPage();
    fillAndSubmitLoginForm('   ', '123');

    await screen.findByText('Request validation failed');
    expect(mockedSetAccessToken).not.toHaveBeenCalled();
  });

  test('account_already_logged_in with refresh token shows restore option', async () => {
    let refreshTokenValue: string | null = null;
    mockedGetRefreshToken.mockImplementation(() => refreshTokenValue);
    mockedHttpRequest.mockResolvedValueOnce({
      ok: false,
      success: false,
      data: null,
      message: null,
      error: {
        code: 'account_already_logged_in',
        message: 'Account is already logged in on another device',
      },
    });

    renderLoginPage();
    refreshTokenValue = 'refresh-token';
    fillAndSubmitLoginForm('ue2e_student_owner', '123');

    expect(await screen.findByText('Tài khoản đang có phiên đăng nhập khác. Nếu đây là cùng máy thi vừa bị tắt trình duyệt, vui lòng thử khôi phục phiên hoặc liên hệ giám thị.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Khôi phục phiên đăng nhập' })).toBeInTheDocument();
    expect(screen.getByLabelText(/^mật khẩu$/i, { selector: 'input' })).toHaveValue('');
  });

  test('account_already_logged_in without refresh token shows contact guidance', async () => {
    mockedHttpRequest.mockResolvedValueOnce({
      ok: false,
      success: false,
      data: null,
      message: null,
      error: {
        code: 'account_already_logged_in',
        message: 'Account is already logged in on another device',
      },
    });

    renderLoginPage();
    fillAndSubmitLoginForm('ue2e_student_owner', '123');

    expect(await screen.findByText('Nếu đây không phải cùng máy thi còn phiên hoạt động, vui lòng liên hệ giám thị hoặc quản trị viên.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Khôi phục phiên đăng nhập' })).not.toBeInTheDocument();
  });

  test('restore option calls restore flow and redirects on success', async () => {
    let refreshTokenValue: string | null = null;
    mockedGetRefreshToken.mockImplementation(() => refreshTokenValue);
    mockedHttpRequest
      .mockResolvedValueOnce({
        ok: false,
        success: false,
        data: null,
        message: null,
        error: {
          code: 'account_already_logged_in',
          message: 'Account is already logged in on another device',
        },
      })
      .mockResolvedValueOnce({
        ok: true,
        success: true,
        data: {
          user_id: 2,
          username: 'student',
          display_name: 'Student',
          roles: ['STUDENT'],
          permissions: [],
          active: true,
        },
        message: null,
        error: null,
      });

    renderLoginPage();
    refreshTokenValue = 'refresh-token';
    fillAndSubmitLoginForm('ue2e_student_owner', '123');

    fireEvent.click(await screen.findByRole('button', { name: 'Khôi phục phiên đăng nhập' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Đang khôi phục phiên đăng nhập...');
    await waitFor(() => expect(mockedHttpRequest).toHaveBeenNthCalledWith(2, '/auth/me'));
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/dashboard', { replace: true }));
  });

  test('restore failure leaves user on login with safe message', async () => {
    let refreshTokenValue: string | null = null;
    mockedGetRefreshToken.mockImplementation(() => refreshTokenValue);
    mockedHttpRequest
      .mockResolvedValueOnce({
        ok: false,
        success: false,
        data: null,
        message: null,
        error: {
          code: 'account_already_logged_in',
          message: 'Account is already logged in on another device',
        },
      })
      .mockResolvedValueOnce({
        ok: false,
        success: false,
        data: null,
        message: null,
        error: {
          code: 'invalid_token',
          message: 'Invalid or expired token',
        },
      });

    renderLoginPage();
    refreshTokenValue = 'refresh-token';
    fillAndSubmitLoginForm('ue2e_student_owner', '123');

    fireEvent.click(await screen.findByRole('button', { name: 'Khôi phục phiên đăng nhập' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Phiên đăng nhập trước không còn hiệu lực. Vui lòng đăng nhập lại.');
    expect(mockedClearAuthTokens).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: /^đăng nhập$/i })).toBeInTheDocument();
    expect(navigateMock).not.toHaveBeenCalledWith('/dashboard', { replace: true });
  });

  test('double submit while request is pending sends only one login request', async () => {
    let resolveRequest: ((value: Awaited<ReturnType<typeof httpRequest>>) => void) | null = null;
    mockedHttpRequest.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve;
        })
    );

    renderLoginPage();
    fireEvent.change(screen.getByLabelText(/tài khoản hoặc email/i), { target: { value: 'ue2e_student_owner' } });
    fireEvent.change(screen.getByLabelText(/^mật khẩu$/i, { selector: 'input' }), { target: { value: '123' } });

    const submitButton = screen.getByRole('button', { name: /^đăng nhập$/i });
    fireEvent.click(submitButton);
    fireEvent.click(submitButton);

    await waitFor(() => expect(mockedHttpRequest).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(submitButton).toBeDisabled());

    resolveRequest?.({
      ok: false,
      success: false,
      data: null,
      message: null,
      error: {
        code: 'invalid_credentials',
        message: 'Invalid username/email or password',
      },
    });

    await screen.findByRole('alert');
  });

  test('identifier change clears password and stale error', async () => {
    mockedHttpRequest.mockResolvedValue({
      ok: false,
      success: false,
      data: null,
      message: null,
      error: {
        code: 'invalid_credentials',
        message: 'Invalid username/email or password',
      },
    });

    renderLoginPage();
    fillAndSubmitLoginForm('ue2e_student_owner', 'wrong-password');

    expect(await screen.findByRole('alert')).toHaveTextContent('Thông tin đăng nhập chưa đúng. Vui lòng nhập lại mật khẩu.');

    const identifierInput = screen.getByLabelText(/tài khoản hoặc email/i);
    const passwordInput = screen.getByLabelText(/^mật khẩu$/i, { selector: 'input' });
    fireEvent.change(passwordInput, { target: { value: 'still-wrong' } });
    fireEvent.change(identifierInput, { target: { value: 'another-student' } });

    expect(identifierInput).toHaveValue('another-student');
    expect(passwordInput).toHaveValue('');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  test('password change clears stale invalid-credential error', async () => {
    mockedHttpRequest.mockResolvedValue({
      ok: false,
      success: false,
      data: null,
      message: null,
      error: {
        code: 'invalid_credentials',
        message: 'Invalid username/email or password',
      },
    });

    renderLoginPage();
    fillAndSubmitLoginForm('ue2e_student_owner', 'wrong-password');

    expect(await screen.findByRole('alert')).toHaveTextContent('Thông tin đăng nhập chưa đúng. Vui lòng nhập lại mật khẩu.');

    fireEvent.change(screen.getByLabelText(/^mật khẩu$/i, { selector: 'input' }), { target: { value: 'new-password' } });

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  test('renders public settings in header and footer', () => {
    renderLoginPage();

    expect(screen.getByTestId('academy-name')).toHaveTextContent('Học viện Công nghệ Bưu chính Viễn thông');
    expect(screen.getByAltText('Học viện Công nghệ Bưu chính Viễn thông')).toHaveAttribute('src', 'https://assets.local/logo.png');
    expect(screen.getByTestId('support-info')).toHaveTextContent('Hỗ trợ kỹ thuật: Email: support@academy.edu.vn | Hotline: 0123-456-789');
  });

  test('falls back to default settings gracefully when public settings fail and login is still functional', async () => {
    mockedUsePublicSettings.mockReturnValue({
      settings: {
        academy_name: 'Trường Đại học Mặc định',
        portal_logo_url: '',
        exam_regulations: '',
        support_email: 'fallback@academy.edu.vn',
        support_hotline: '1900-1111',
      },
      loading: false,
      error: 'Failed to load settings',
    });

    renderLoginPage();

    expect(screen.getByTestId('academy-name')).toHaveTextContent('Trường Đại học Mặc định');
    expect(screen.getByTestId('support-info')).toHaveTextContent('Hỗ trợ kỹ thuật: Email: fallback@academy.edu.vn | Hotline: 1900-1111');

    mockedHttpRequest.mockResolvedValue({
      ok: true,
      success: true,
      data: {
        access_token: 'student-access-token',
        refresh_token: 'student-refresh-token',
        user: {
          user_id: 2,
          username: 'student',
          roles: ['STUDENT'],
        },
      },
      message: null,
      error: null,
    });

    fillAndSubmitLoginForm('ue2e_student_owner', '123');

    await waitFor(() => expect(mockedSetAccessToken).toHaveBeenCalledWith('student-access-token'));
    expect(mockedSetRefreshToken).toHaveBeenCalledWith('student-refresh-token');
    expect(navigateMock).toHaveBeenCalledWith('/dashboard');
  });
});
