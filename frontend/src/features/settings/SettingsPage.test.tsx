import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { httpRequest } from '../../shared/api/httpClient';
import { SettingsPage } from './SettingsPage';
import { usePublicSettings } from './usePublicSettings';
import { SupportInfoWidget } from './components/SupportInfoWidget';
import { ExamRegulationsPanel } from './components/ExamRegulationsPanel';
import { DEFAULT_PUBLIC_SETTINGS } from './settingsDefaults';
import { loadPublicSettings } from './publicSettingsApi';

vi.mock('../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

// Mock window.confirm
const mockConfirm = vi.fn().mockReturnValue(true);
window.confirm = mockConfirm;

const mockedHttpRequest = vi.mocked(httpRequest);

function okEnvelope<T>(data: T) {
  return {
    ok: true as const,
    success: true as const,
    data,
    message: null,
    error: null,
  };
}

function errorEnvelope(message: string, code = 'error') {
  return {
    ok: false as const,
    success: false as const,
    data: null as any,
    message,
    error: {
      code,
      message,
    },
  };
}

function validationErrorEnvelope(errors: Array<{ loc: unknown[]; msg: string; type?: string }>) {
  return {
    ok: false as const,
    success: false as const,
    data: null as any,
    message: null,
    error: {
      code: 'validation_error',
      message: 'Request validation failed',
      details: {
        errors,
      },
    },
  };
}

const defaultSettings = {
  academy_name: 'Trường Đại học Công nghệ',
  portal_logo_url: 'https://assets.local/logo.png',
  exam_regulations: '1. Không gian lận.\n2. Không sử dụng tài liệu.',
  support_email: 'support@university.edu.vn',
  support_hotline: '19001000',
  session_heartbeat_seconds: 30,
  concurrent_login_check: true,
  autosave_interval_seconds: 10,
  exam_start_window_minutes: 15,
  late_entry_window_minutes: 10,
  min_proctors_per_room: 1,
  max_sessions_per_proctor_per_day: 3,
  updated_at: '2026-05-21T07:00:00Z',
  updated_by: 101,
  version: 1,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockConfirm.mockClear();
  localStorage.clear();
});

describe('SettingsPage UI and validations', () => {
  test('shows loading state before settings load completes', () => {
    mockedHttpRequest.mockImplementationOnce(
      () => new Promise(() => undefined)
    );

    render(<SettingsPage />);

    expect(screen.getByText('Đang tải cấu hình hệ thống...')).toBeInTheDocument();
  });

  test('loads and displays current system settings', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);

    expect(await screen.findByLabelText(/Tên Học viện \/ Trường/)).toHaveValue('Trường Đại học Công nghệ');
    expect(screen.getByLabelText('Đường dẫn ảnh Logo (URL)')).toHaveValue('https://assets.local/logo.png');
    expect(screen.getByLabelText(/Email hỗ trợ/)).toHaveValue('support@university.edu.vn');
    expect(screen.getByLabelText(/Hotline hỗ trợ kỹ thuật/)).toHaveValue('19001000');
    expect(screen.getByLabelText(/Nội quy \/ Hướng dẫn phòng thi \(Plain text\)/)).toHaveValue(
      '1. Không gian lận.\n2. Không sử dụng tài liệu.'
    );
    expect(screen.getByLabelText(/Tần suất gửi tín hiệu duy trì phiên \(Heartbeat - giây\)/)).toHaveValue(30);
    expect(screen.getByLabelText('Ngăn chặn đăng nhập đồng thời trên nhiều thiết bị')).toBeChecked();

    expect(mockedHttpRequest).toHaveBeenCalledWith('/admin/system/settings', { method: 'GET' });
  });

  test('renders compact sections and compact audit metadata region', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);

    await screen.findByLabelText(/Tên Học viện \/ Trường/);

    expect(screen.getByTestId('settings-page')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Thông tin tổ chức & Thương hiệu' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Quy chế phòng thi' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Audit metadata' })).toBeInTheDocument();
    expect(screen.getByText(/Phiên bản cấu hình:/)).toBeInTheDocument();
    expect(screen.queryByText('Real API mode')).not.toBeInTheDocument();
    expect(screen.getByText(/Dirty state:/)).toBeInTheDocument();
    expect(screen.getByText(/Version guard:/)).toBeInTheDocument();
  });

  test('keeps save action text-visible while refresh action stays compact icon control', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);

    await screen.findByLabelText(/Tên Học viện \/ Trường/);

    expect(screen.getByRole('button', { name: 'Làm mới dữ liệu' })).toHaveClass('compact-icon-action');
    expect(screen.getByRole('button', { name: 'Lưu cấu hình' })).not.toHaveClass('compact-icon-action');
  });

  test('marks required settings fields in the form labels', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);

    await screen.findByLabelText(/Tên Học viện \/ Trường/);

    expect(screen.getByText('Tên Học viện / Trường', { selector: 'label' })).toHaveTextContent('Tên Học viện / Trường*');
    expect(screen.getByText('Email hỗ trợ', { selector: 'label' })).toHaveTextContent('Email hỗ trợ*');
    expect(screen.getByText('Hotline hỗ trợ kỹ thuật', { selector: 'label' })).toHaveTextContent('Hotline hỗ trợ kỹ thuật*');
    expect(screen.getByText('Tần suất gửi tín hiệu duy trì phiên (Heartbeat - giây)', { selector: 'label' })).toHaveTextContent(
      'Tần suất gửi tín hiệu duy trì phiên (Heartbeat - giây)*'
    );
  });

  test('load failure shows error panel and retry button', async () => {
    mockedHttpRequest.mockResolvedValueOnce(errorEnvelope('Resource not found', 'not_found'));

    render(<SettingsPage />);

    expect(await screen.findByRole('heading', { name: 'Không tải được cấu hình hệ thống' })).toBeInTheDocument();
    expect(screen.getByText('Resource not found')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Tải lại cấu hình' })).toBeInTheDocument();
  });

  test('load failure does not show enabled save button after load fails', async () => {
    mockedHttpRequest.mockResolvedValueOnce(errorEnvelope('Resource not found', 'not_found'));

    render(<SettingsPage />);

    await screen.findByText('Resource not found');
    expect(screen.queryByRole('button', { name: 'Lưu cấu hình' })).not.toBeInTheDocument();
    expect(screen.getByText('Không thể lưu cấu hình khi dữ liệu chưa tải thành công. Hãy tải lại cấu hình trước khi chỉnh sửa.')).toBeInTheDocument();
  });

  test('save button is enabled only after successful load and actual dirty change', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);

    const submitButton = await screen.findByRole('button', { name: 'Lưu cấu hình' });
    expect(submitButton).toBeDisabled();

    fireEvent.change(screen.getByRole('textbox', { name: /Tên Học viện \/ Trường/i }), { target: { value: 'Đại học Quốc gia' } });

    expect(screen.getByRole('button', { name: 'Lưu cấu hình' })).toBeEnabled();
  });

  test('api 404 message is displayed clearly on load failure', async () => {
    mockedHttpRequest.mockResolvedValueOnce(errorEnvelope('Resource not found', 'not_found'));

    render(<SettingsPage />);

    expect(await screen.findByText('Resource not found')).toBeInTheDocument();
  });

  test('backend validation error maps field errors after save attempt', async () => {
    mockedHttpRequest
      .mockResolvedValueOnce(okEnvelope(defaultSettings))
      .mockResolvedValueOnce(
        validationErrorEnvelope([
          { loc: ['body', 'portal_logo_url'], msg: 'Branding logo URL must use HTTPS protocol' },
          { loc: ['body', 'support_email'], msg: 'value is not a valid email address' },
        ])
      );

    render(<SettingsPage />);

    const nameInput = await screen.findByLabelText(/Tên Học viện \/ Trường/);
    fireEvent.change(nameInput, { target: { value: 'Trường Đại học Công nghệ Mới' } });

    const saveButton = screen.getByRole('button', { name: 'Lưu cấu hình' });
    fireEvent.click(saveButton);

    expect(await screen.findByText('Dữ liệu gửi lên không hợp lệ. Vui lòng kiểm tra các trường được đánh dấu lỗi.')).toBeInTheDocument();
    expect(screen.getByText('Branding logo URL must use HTTPS protocol')).toBeInTheDocument();
    expect(screen.getByText('value is not a valid email address')).toBeInTheDocument();
  });

  test('retry calls loadSystemSettings again', async () => {
    mockedHttpRequest
      .mockResolvedValueOnce(errorEnvelope('Resource not found', 'not_found'))
      .mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Tải lại cấu hình' }));

    expect(await screen.findByLabelText(/Tên Học viện \/ Trường/)).toHaveValue('Trường Đại học Công nghệ');
    expect(mockedHttpRequest).toHaveBeenNthCalledWith(1, '/admin/system/settings', { method: 'GET' });
    expect(mockedHttpRequest).toHaveBeenNthCalledWith(2, '/admin/system/settings', { method: 'GET' });
  });

  test('validates required academy name', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);
    const nameInput = await screen.findByLabelText(/Tên Học viện \/ Trường/);
    fireEvent.change(nameInput, { target: { value: '' } });

    const submitButton = screen.getByRole('button', { name: 'Lưu cấu hình' });
    fireEvent.click(submitButton);

    expect(await screen.findByText('Tên học viện/trường không được để trống.')).toBeInTheDocument();
    expect(mockedHttpRequest).not.toHaveBeenCalledWith('/admin/system/settings', expect.objectContaining({ method: 'PUT' }));
  });

  test('validates email pattern', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);
    const emailInput = await screen.findByLabelText(/Email hỗ trợ/);
    fireEvent.change(emailInput, { target: { value: 'invalid-email' } });

    const submitButton = screen.getByRole('button', { name: 'Lưu cấu hình' });
    fireEvent.click(submitButton);

    expect(await screen.findByText('Địa chỉ email hỗ trợ không hợp lệ.')).toBeInTheDocument();
    expect(mockedHttpRequest).not.toHaveBeenCalledWith('/admin/system/settings', expect.objectContaining({ method: 'PUT' }));
  });

  test('validates heartbeat bounds', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);
    const heartbeatInput = await screen.findByLabelText(/Tần suất gửi tín hiệu duy trì phiên \(Heartbeat - giây\)/);
    fireEvent.change(heartbeatInput, { target: { value: '2' } });

    const submitButton = screen.getByRole('button', { name: 'Lưu cấu hình' });
    fireEvent.click(submitButton);

    expect(await screen.findByText(
      'Tần suất gửi tín hiệu (Heartbeat) phải nằm trong khoảng từ 5 đến 300 giây.'
    )).toBeInTheDocument();
    expect(mockedHttpRequest).not.toHaveBeenCalledWith('/admin/system/settings', expect.objectContaining({ method: 'PUT' }));
  });

  test('validates runtime constraints', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);

    const startWindowInput = await screen.findByLabelText(/Mở đề trước giờ thi \(Phút\)/);
    fireEvent.change(startWindowInput, { target: { value: '150' } });

    const submitButton = screen.getByRole('button', { name: 'Lưu cấu hình' });
    fireEvent.click(submitButton);

    expect(await screen.findByText(
      'Cửa sổ thời gian bắt đầu thi phải nằm trong khoảng từ 0 đến 120 phút.'
    )).toBeInTheDocument();
  });

  test('submits valid changes and displays success message', async () => {
    mockedHttpRequest
      .mockResolvedValueOnce(okEnvelope(defaultSettings))
      .mockResolvedValueOnce(okEnvelope({
        ...defaultSettings,
        academy_name: 'Đại học Quốc gia',
        session_heartbeat_seconds: 45,
      }));

    render(<SettingsPage />);
    const nameInput = await screen.findByLabelText(/Tên Học viện \/ Trường/);
    const heartbeatInput = screen.getByLabelText(/Tần suất gửi tín hiệu duy trì phiên \(Heartbeat - giây\)/);

    fireEvent.change(nameInput, { target: { value: 'Đại học Quốc gia' } });
    fireEvent.change(heartbeatInput, { target: { value: '45' } });

    const submitButton = screen.getByRole('button', { name: 'Lưu cấu hình' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockedHttpRequest).toHaveBeenCalledWith('/admin/system/settings', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          academy_name: 'Đại học Quốc gia',
          portal_logo_url: 'https://assets.local/logo.png',
          exam_regulations: '1. Không gian lận.\n2. Không sử dụng tài liệu.',
          support_email: 'support@university.edu.vn',
          support_hotline: '19001000',
          session_heartbeat_seconds: 45,
          concurrent_login_check: true,
          autosave_interval_seconds: 10,
          exam_start_window_minutes: 15,
          late_entry_window_minutes: 10,
          min_proctors_per_room: 1,
          max_sessions_per_proctor_per_day: 3,
          version: 1,
        }),
      }));
    });

    const putCall = mockedHttpRequest.mock.calls.find(([, options]) => options?.method === 'PUT');
    expect(putCall).toBeDefined();
    expect(String(putCall?.[1]?.body)).not.toContain('updated_at');
    expect(String(putCall?.[1]?.body)).not.toContain('updated_by');

    expect(await screen.findByText('Đã cập nhật cấu hình hệ thống thành công.')).toBeInTheDocument();
  });

  test('Missing version blocks save in real API mode', async () => {
    const { version, ...settingsNoVersion } = defaultSettings;
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(settingsNoVersion));

    render(<SettingsPage />);

    // Make the form dirty to enable the save button
    const nameInput = await screen.findByLabelText(/Tên Học viện \/ Trường/);
    fireEvent.change(nameInput, { target: { value: 'New Academy' } });

    const submitButton = screen.getByRole('button', { name: 'Lưu cấu hình' });
    fireEvent.click(submitButton);

    expect(await screen.findByText(
      'Không thể lưu cấu hình do thiếu thông tin phiên bản (version) trong chế độ API thật.'
    )).toBeInTheDocument();
    expect(mockedHttpRequest).not.toHaveBeenCalledWith('/admin/system/settings', expect.objectContaining({ method: 'PUT' }));
  });

  test('Admin settings API failure does not show false success', async () => {
    mockedHttpRequest
      .mockResolvedValueOnce(okEnvelope(defaultSettings))
      .mockResolvedValueOnce(errorEnvelope('Lỗi kết nối máy chủ.'));

    render(<SettingsPage />);
    const nameInput = await screen.findByLabelText(/Tên Học viện \/ Trường/);
    fireEvent.change(nameInput, { target: { value: 'Đại học Quốc gia' } });

    const submitButton = screen.getByRole('button', { name: 'Lưu cấu hình' });
    fireEvent.click(submitButton);

    expect(await screen.findByText('Lỗi kết nối máy chủ.')).toBeInTheDocument();
    expect(screen.queryByText('Đã cập nhật cấu hình hệ thống thành công.')).not.toBeInTheDocument();
  });

  test('validates HTTPS preference for portal logo url', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);
    const logoInput = await screen.findByLabelText('Đường dẫn ảnh Logo (URL)');
    fireEvent.change(logoInput, { target: { value: 'http://assets.local/logo.png' } });

    const submitButton = screen.getByRole('button', { name: 'Lưu cấu hình' });
    fireEvent.click(submitButton);

    expect(await screen.findByText('Đường dẫn logo phải sử dụng giao thức bảo mật HTTPS.')).toBeInTheDocument();
    expect(mockedHttpRequest).not.toHaveBeenCalledWith('/admin/system/settings', expect.objectContaining({ method: 'PUT' }));
  });

  test('allows min proctors and max sessions to exceed 10 and 12', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope({ ...defaultSettings, min_proctors_per_room: 11, max_sessions_per_proctor_per_day: 13 }));

    render(<SettingsPage />);
    const minProctorsInput = await screen.findByRole('spinbutton', { name: /Số cán bộ coi thi tối thiểu mỗi phòng/i });
    const maxSessionsInput = screen.getByRole('spinbutton', { name: /Số ca thi tối đa của giám thị mỗi ngày/i });

    fireEvent.change(minProctorsInput, { target: { value: '11' } });
    fireEvent.change(maxSessionsInput, { target: { value: '13' } });

    const submitButton = screen.getByRole('button', { name: 'Lưu cấu hình' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockedHttpRequest).toHaveBeenLastCalledWith('/admin/system/settings', expect.objectContaining({
        method: 'PUT',
        body: expect.stringContaining('"min_proctors_per_room":11'),
      }));
    });
  });


  test('renders regulations editor label and validates required and max-length', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);
    const regulationsLabel = await screen.findByText('Nội quy / Hướng dẫn phòng thi (Plain text)');
    expect(regulationsLabel).toBeInTheDocument();

    const regulationsInput = screen.getByRole('textbox', { name: /Nội quy \/ Hướng dẫn phòng thi \(Plain text\)/i });
    
    // Test required validation
    fireEvent.change(regulationsInput, { target: { value: '' } });
    const submitButton = screen.getByRole('button', { name: 'Lưu cấu hình' });
    fireEvent.click(submitButton);
    expect(await screen.findByText('Nội quy / Hướng dẫn phòng thi không được để trống.')).toBeInTheDocument();

    // Test max length validation
    fireEvent.change(regulationsInput, { target: { value: 'a'.repeat(10001) } });
    fireEvent.click(submitButton);
    expect(await screen.findByText('Nội quy / Hướng dẫn phòng thi không được vượt quá 10000 ký tự.')).toBeInTheDocument();
  });

  test('validates lower limits for min proctors and max sessions', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);
    const minProctorsInput = await screen.findByRole('spinbutton', { name: /Số cán bộ coi thi tối thiểu mỗi phòng/i });
    const maxSessionsInput = screen.getByRole('spinbutton', { name: /Số ca thi tối đa của giám thị mỗi ngày/i });

    fireEvent.change(minProctorsInput, { target: { value: '0' } });
    fireEvent.change(maxSessionsInput, { target: { value: '0' } });

    const submitButton = screen.getByRole('button', { name: 'Lưu cấu hình' });
    fireEvent.click(submitButton);

    expect(await screen.findByText('Số cán bộ coi thi tối thiểu phải từ 1 người trở lên.')).toBeInTheDocument();
    expect(await screen.findByText('Số ca thi tối đa của giám thị phải từ 1 ca trở lên.')).toBeInTheDocument();
    expect(mockedHttpRequest).not.toHaveBeenCalledWith('/admin/system/settings', expect.objectContaining({ method: 'PUT' }));
  });

  test('validates support hotline is required', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);
    const hotlineInput = await screen.findByRole('textbox', { name: /Hotline hỗ trợ kỹ thuật/i });
    fireEvent.change(hotlineInput, { target: { value: '' } });

    const submitButton = screen.getByRole('button', { name: 'Lưu cấu hình' });
    fireEvent.click(submitButton);

    expect(await screen.findByText('Hotline hỗ trợ không được để trống.')).toBeInTheDocument();
  });

  test('validates late entry window bounds', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);
    const lateEntryInput = await screen.findByRole('spinbutton', { name: /Thời gian đi trễ tối đa \(Phút\)/i });
    
    // Value 121 should fail
    fireEvent.change(lateEntryInput, { target: { value: '121' } });
    const submitButton = screen.getByRole('button', { name: 'Lưu cấu hình' });
    fireEvent.click(submitButton);
    expect(await screen.findByText('Thời gian trễ tối đa cho phép phải nằm trong khoảng từ 0 đến 120 phút.')).toBeInTheDocument();
  });

  test('accepts a valid complex HTTPS logo URL', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);
    const logoInput = await screen.findByLabelText('Đường dẫn ảnh Logo (URL)');
    
    // Complex HTTPS URL with query strings, port, and subdomains
    const complexUrl = 'https://sub.domain-name.co.uk:8080/path/to/image.png?key=val&other=123#fragment-id';
    fireEvent.change(logoInput, { target: { value: complexUrl } });

    const submitButton = screen.getByRole('button', { name: 'Lưu cấu hình' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockedHttpRequest).toHaveBeenLastCalledWith('/admin/system/settings', expect.objectContaining({
        method: 'PUT',
        body: expect.stringContaining(JSON.stringify(complexUrl)),
      }));
    });
  });

  test('accepts support hotline with arbitrary characters within 50 chars limit', async () => {
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));
    mockedHttpRequest.mockResolvedValueOnce(okEnvelope(defaultSettings));

    render(<SettingsPage />);
    const hotlineInput = await screen.findByRole('textbox', { name: /Hotline hỗ trợ kỹ thuật/i });
    
    // Hotline with text/letters and length <= 50
    const complexHotline = 'HOTLINE-1234 (Support: 24/7)';
    fireEvent.change(hotlineInput, { target: { value: complexHotline } });

    const submitButton = screen.getByRole('button', { name: 'Lưu cấu hình' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockedHttpRequest).toHaveBeenLastCalledWith('/admin/system/settings', expect.objectContaining({
        method: 'PUT',
        body: expect.stringContaining(JSON.stringify(complexHotline)),
      }));
    });
  });
});

describe('usePublicSettings Hook', () => {
  test('returns fallback defaults when public API fails', async () => {
    mockedHttpRequest.mockResolvedValueOnce(errorEnvelope('Network Error'));

    function TestComponent() {
      const { settings, loading } = usePublicSettings();
      if (loading) return <div>Loading...</div>;
      return <div data-testid="academy">{settings.academy_name}</div>;
    }

    render(<TestComponent />);
    expect(await screen.findByTestId('academy')).toHaveTextContent(DEFAULT_PUBLIC_SETTINGS.academy_name);
  });
});

describe('SupportInfoWidget', () => {
  test('renders email and hotline', () => {
    render(<SupportInfoWidget email="test@test.com" hotline="12345" />);
    expect(screen.getByText('test@test.com')).toBeInTheDocument();
    expect(screen.getByText('12345')).toBeInTheDocument();
  });
});

describe('ExamRegulationsPanel XSS Safety', () => {
  test('renders regulations as inert plain text and does not execute html', () => {
    const maliciousText = '<script>alert("hack")</script><div id="xss">Test</div>';
    render(<ExamRegulationsPanel regulationsText={maliciousText} />);

    expect(screen.getByText(maliciousText)).toBeInTheDocument();
    const xssDiv = document.getElementById('xss');
    expect(xssDiv).toBeNull();
  });
});

describe('publicSettingsApi', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  test('does not read mock localStorage unless mock mode is enabled', async () => {
    const mockSettings = {
      academy_name: 'Stale Academy Name from Mock LocalStorage',
      portal_logo_url: 'http://stale.com/logo.png',
      exam_regulations: 'Stale regulations',
      support_email: 'stale@stale.com',
      support_hotline: '999999',
    };
    localStorage.setItem('mock_admin_runtime_settings', JSON.stringify(mockSettings));
    localStorage.setItem('use_mock_settings_api', 'false');

    mockedHttpRequest.mockResolvedValueOnce(errorEnvelope('API Offline', '500'));

    const response = await loadPublicSettings();

    expect(response.ok).toBe(false);
    expect(response.data).toBeNull();
  });

  test('reads mock localStorage when mock mode is enabled', async () => {
    const mockSettings = {
      academy_name: 'Academy from Mock LocalStorage',
      portal_logo_url: 'https://mock.com/logo.png',
      exam_regulations: 'Mock regulations',
      support_email: 'mock@mock.com',
      support_hotline: '123456',
    };
    localStorage.setItem('mock_admin_runtime_settings', JSON.stringify(mockSettings));
    localStorage.setItem('use_mock_settings_api', 'true');

    const response = await loadPublicSettings();

    expect(response.ok).toBe(true);
    expect(response.data?.academy_name).toBe('Academy from Mock LocalStorage');
  });

  test('fallback uses DEFAULT_PUBLIC_SETTINGS when API fails in non-mock mode', async () => {
    localStorage.setItem('use_mock_settings_api', 'false');
    mockedHttpRequest.mockResolvedValueOnce(errorEnvelope('API Offline'));

    const response = await loadPublicSettings();

    expect(response.ok).toBe(false);
  });
});
