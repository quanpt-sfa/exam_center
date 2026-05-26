import { FormEvent, useEffect, useState } from 'react';
import { loadSystemSettings, updateSystemSettings, isMockModeEnabled, type AdminRuntimeSettings } from './settingsApi';
import { SettingsSectionCard } from './components/SettingsSectionCard';
import { SettingsFieldRow } from './components/SettingsFieldRow';
import { LogoPreview } from './components/LogoPreview';
import { ExamRegulationsEditor } from './components/ExamRegulationsEditor';
import { SettingsAuditMeta } from './components/SettingsAuditMeta';
import { SaveSettingsBar } from './components/SaveSettingsBar';
import { CompactPage } from '../../shared/components/compact/CompactPage';
import { ApiStatusChip } from '../../shared/components/compact/ApiStatusChip';
import { CompactPageHeader } from '../../shared/components/compact/CompactPageHeader';
import { CompactToolbar } from '../../shared/components/compact/CompactToolbar';
import { IconActionButton } from '../../shared/components/compact/IconActionButton';
import { CompactFormGrid } from './components/CompactFormPrimitives';
import { isUiApiDiagnosticsEnabled } from '../../shared/uiDiagnostics';

type ValidationErrorEntry = {
  loc?: unknown;
  msg?: unknown;
};

function extractBackendValidationErrors(details: unknown): Record<string, string> {
  if (!details || typeof details !== 'object' || !('errors' in details)) {
    return {};
  }

  const rawErrors = (details as { errors?: unknown }).errors;
  if (!Array.isArray(rawErrors)) {
    return {};
  }

  const fieldErrors: Record<string, string> = {};
  for (const rawError of rawErrors as ValidationErrorEntry[]) {
    const loc = Array.isArray(rawError.loc) ? rawError.loc : [];
    const field = typeof loc[loc.length - 1] === 'string' ? String(loc[loc.length - 1]) : null;
    const message = typeof rawError.msg === 'string' ? rawError.msg : null;
    if (!field || !message || field in fieldErrors) {
      continue;
    }
    fieldErrors[field] = message;
  }

  return fieldErrors;
}

export function SettingsPage() {
  const [initialSettings, setInitialSettings] = useState<AdminRuntimeSettings | null>(null);
  const [settings, setSettings] = useState<AdminRuntimeSettings>({
    academy_name: '',
    portal_logo_url: '',
    exam_regulations: '',
    support_email: '',
    support_hotline: '',
    session_heartbeat_seconds: 30,
    concurrent_login_check: true,
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  async function fetchSettings() {
    setLoading(true);
    setLoadError(null);
    setError(null);
    setSuccess(null);
    setValidationErrors({});

    const response = await loadSystemSettings();
    setLoading(false);

    if (!response.ok) {
      setInitialSettings(null);
      setLoadError(response.error.message);
      return;
    }

    setInitialSettings(response.data);
    setSettings(response.data);
  }

  useEffect(() => {
    void fetchSettings();
  }, []);

  const handleInputChange = (key: keyof AdminRuntimeSettings, value: unknown) => {
    setSettings((prev) => ({
      ...prev,
      [key]: value,
    }));

    if (validationErrors[key]) {
      setValidationErrors((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  };

  const getIsDirty = (): boolean => {
    if (!initialSettings) return false;

    const keys: Array<keyof AdminRuntimeSettings> = [
      'academy_name',
      'portal_logo_url',
      'exam_regulations',
      'support_email',
      'support_hotline',
      'session_heartbeat_seconds',
      'concurrent_login_check',
      'autosave_interval_seconds',
      'exam_start_window_minutes',
      'late_entry_window_minutes',
      'min_proctors_per_room',
      'max_sessions_per_proctor_per_day',
    ];

    for (const key of keys) {
      const initVal = initialSettings[key];
      const curVal = settings[key];
      if (initVal !== curVal) {
        return true;
      }
    }

    return false;
  };

  const isDirty = getIsDirty();
  const validationSummary = Object.entries(validationErrors);
  const showApiDiagnostics = isUiApiDiagnosticsEnabled();

  const handleReset = () => {
    if (!initialSettings) {
      return;
    }

    setSettings(initialSettings);
    setValidationErrors({});
    setError(null);
    setSuccess(null);
  };

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!initialSettings) {
      setError('Không thể lưu cấu hình khi dữ liệu chưa tải thành công.');
      return;
    }

    setError(null);
    setSuccess(null);

    if (!isMockModeEnabled() && settings.version === undefined) {
      setError('Không thể lưu cấu hình do thiếu thông tin phiên bản (version) trong chế độ API thật.');
      return;
    }

    const errors: Record<string, string> = {};

    if (!settings.academy_name.trim()) {
      errors.academy_name = 'Tên học viện/trường không được để trống.';
    } else if (settings.academy_name.length > 255) {
      errors.academy_name = 'Tên học viện/trường không được vượt quá 255 ký tự.';
    }

    if (!settings.exam_regulations.trim()) {
      errors.exam_regulations = 'Nội quy / Hướng dẫn phòng thi không được để trống.';
    } else if (settings.exam_regulations.length > 10000) {
      errors.exam_regulations = 'Nội quy / Hướng dẫn phòng thi không được vượt quá 10000 ký tự.';
    }

    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!settings.support_email.trim()) {
      errors.support_email = 'Email hỗ trợ không được để trống.';
    } else if (settings.support_email.length < 3 || settings.support_email.length > 255) {
      errors.support_email = 'Email hỗ trợ phải có độ dài từ 3 đến 255 ký tự.';
    } else if (!emailPattern.test(settings.support_email)) {
      errors.support_email = 'Địa chỉ email hỗ trợ không hợp lệ.';
    }

    if (!settings.support_hotline || !settings.support_hotline.trim()) {
      errors.support_hotline = 'Hotline hỗ trợ không được để trống.';
    } else if (settings.support_hotline.length > 50) {
      errors.support_hotline = 'Hotline hỗ trợ không được vượt quá 50 ký tự.';
    }

    if (settings.portal_logo_url) {
      if (settings.portal_logo_url.length > 2000) {
        errors.portal_logo_url = 'Đường dẫn logo không được vượt quá 2000 ký tự.';
      } else if (!settings.portal_logo_url.startsWith('https://')) {
        errors.portal_logo_url = 'Đường dẫn logo phải sử dụng giao thức bảo mật HTTPS.';
      }
    }

    if (
      settings.session_heartbeat_seconds === undefined ||
      settings.session_heartbeat_seconds === null ||
      isNaN(settings.session_heartbeat_seconds)
    ) {
      errors.session_heartbeat_seconds = 'Tần suất gửi tín hiệu duy trì phiên không được để trống.';
    } else if (settings.session_heartbeat_seconds < 5 || settings.session_heartbeat_seconds > 300) {
      errors.session_heartbeat_seconds = 'Tần suất gửi tín hiệu (Heartbeat) phải nằm trong khoảng từ 5 đến 300 giây.';
    }

    if (
      settings.autosave_interval_seconds === undefined ||
      settings.autosave_interval_seconds === null ||
      isNaN(settings.autosave_interval_seconds)
    ) {
      errors.autosave_interval_seconds = 'Thời gian tự động lưu bài không được để trống.';
    } else if (settings.autosave_interval_seconds < 5 || settings.autosave_interval_seconds > 120) {
      errors.autosave_interval_seconds = 'Thời gian tự động lưu bài phải nằm trong khoảng từ 5 đến 120 giây.';
    }

    if (
      settings.exam_start_window_minutes === undefined ||
      settings.exam_start_window_minutes === null ||
      isNaN(settings.exam_start_window_minutes)
    ) {
      errors.exam_start_window_minutes = 'Thời gian mở đề trước giờ thi không được để trống.';
    } else if (settings.exam_start_window_minutes < 0 || settings.exam_start_window_minutes > 120) {
      errors.exam_start_window_minutes = 'Cửa sổ thời gian bắt đầu thi phải nằm trong khoảng từ 0 đến 120 phút.';
    }

    if (
      settings.late_entry_window_minutes === undefined ||
      settings.late_entry_window_minutes === null ||
      isNaN(settings.late_entry_window_minutes)
    ) {
      errors.late_entry_window_minutes = 'Thời gian trễ tối đa cho phép không được để trống.';
    } else if (settings.late_entry_window_minutes < 0 || settings.late_entry_window_minutes > 120) {
      errors.late_entry_window_minutes = 'Thời gian trễ tối đa cho phép phải nằm trong khoảng từ 0 đến 120 phút.';
    }

    if (
      settings.min_proctors_per_room === undefined ||
      settings.min_proctors_per_room === null ||
      isNaN(settings.min_proctors_per_room)
    ) {
      errors.min_proctors_per_room = 'Số cán bộ coi thi tối thiểu không được để trống.';
    } else if (settings.min_proctors_per_room < 1) {
      errors.min_proctors_per_room = 'Số cán bộ coi thi tối thiểu phải từ 1 người trở lên.';
    }

    if (
      settings.max_sessions_per_proctor_per_day === undefined ||
      settings.max_sessions_per_proctor_per_day === null ||
      isNaN(settings.max_sessions_per_proctor_per_day)
    ) {
      errors.max_sessions_per_proctor_per_day = 'Số ca thi tối đa của giám thị không được để trống.';
    } else if (settings.max_sessions_per_proctor_per_day < 1) {
      errors.max_sessions_per_proctor_per_day = 'Số ca thi tối đa của giám thị phải từ 1 ca trở lên.';
    }

    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      setError('Vui lòng kiểm tra lại các trường thông tin bị nhập sai.');
      return;
    }

    const securityChanged =
      initialSettings.session_heartbeat_seconds !== settings.session_heartbeat_seconds ||
      initialSettings.concurrent_login_check !== settings.concurrent_login_check;

    if (securityChanged) {
      const confirmed = window.confirm('Bạn đang thay đổi cấu hình bảo mật phòng thi (Heartbeat / Đăng nhập đồng thời). Tiếp tục lưu?');
      if (!confirmed) {
        return;
      }
    }

    setSaving(true);
    const response = await updateSystemSettings(settings);
    setSaving(false);

    if (!response.ok) {
      if (response.error.code === 'validation_error') {
        const backendFieldErrors = extractBackendValidationErrors(response.error.details);
        if (Object.keys(backendFieldErrors).length > 0) {
          setValidationErrors(backendFieldErrors);
          setError('Dữ liệu gửi lên không hợp lệ. Vui lòng kiểm tra các trường được đánh dấu lỗi.');
          return;
        }
      }

      setError(response.error.message);
      return;
    }

    setSuccess('Đã cập nhật cấu hình hệ thống thành công.');
    setInitialSettings(response.data);
    setSettings(response.data);
  }

  return (
    <CompactPage className="settings-page" data-testid="settings-page">
      <CompactPageHeader
        eyebrow="Hệ thống"
        title="Cấu hình hệ thống"
        description="Thiết lập thông tin thương hiệu, quy chế thi, kênh hỗ trợ và cấu hình an toàn thời gian chạy."
        primaryActions={
          <IconActionButton
            icon="refresh"
            label={loading ? 'Đang tải...' : 'Làm mới dữ liệu'}
            onClick={() => void fetchSettings()}
            disabled={loading || saving}
          />
        }
      />

      <CompactToolbar className="settings-status-toolbar">
        {showApiDiagnostics ? (
          <ApiStatusChip
            status={isMockModeEnabled() ? 'partial' : 'connected'}
            label={isMockModeEnabled() ? 'Mock API mode' : 'Real API mode'}
          />
        ) : null}
        <span className="muted">Dirty state: {isDirty ? 'Unsaved changes' : 'No pending change'}</span>
        <span className="muted">Version guard: {settings.version !== undefined ? `v${settings.version}` : 'Missing version'}</span>
      </CompactToolbar>

      {loadError ? (
        <section className="settings-alert settings-alert--danger" role="alert" aria-live="polite">
          <h3>Không tải được cấu hình hệ thống</h3>
          <p className="error">{loadError}</p>
          <p className="muted">Không thể lưu cấu hình khi dữ liệu chưa tải thành công. Hãy tải lại cấu hình trước khi chỉnh sửa.</p>
          <button type="button" className="primary-button" onClick={() => void fetchSettings()} disabled={loading || saving}>
            Tải lại cấu hình
          </button>
        </section>
      ) : null}

      {error ? (
        <div className="settings-alert settings-alert--danger" role="alert" aria-live="polite">
          {error}
        </div>
      ) : null}

      {success ? (
        <div className="settings-alert settings-alert--success" role="alert" aria-live="polite">
          {success}
        </div>
      ) : null}

      {!loading && validationSummary.length > 0 ? (
        <section className="settings-alert settings-alert--danger" role="alert" aria-live="polite">
          <h3>Các trường cần kiểm tra</h3>
          <ul className="settings-validation-summary-list">
            {validationSummary.map(([field]) => (
              <li key={field}>
                <strong>{field}</strong>: có lỗi cần kiểm tra.
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {loading ? (
        <section className="settings-alert" aria-live="polite">
          <p className="muted">Đang tải cấu hình hệ thống...</p>
        </section>
      ) : !initialSettings ? null : (
        <form onSubmit={handleSubmit} className="settings-form" noValidate>
          <SettingsSectionCard
            title="Thông tin tổ chức & Thương hiệu"
            description="Cấu hình tên cơ sở đào tạo và ảnh đại diện hiển thị ngoài trang đăng nhập."
          >
            <CompactFormGrid>
              <SettingsFieldRow label="Tên Học viện / Trường" htmlFor="academy_name" required={true} error={validationErrors.academy_name}>
                <input
                  id="academy_name"
                  type="text"
                  value={settings.academy_name}
                  onChange={(e) => handleInputChange('academy_name', e.target.value)}
                  placeholder="Ví dụ: Học viện Công nghệ Bưu chính Viễn thông"
                  required
                />
              </SettingsFieldRow>

              <SettingsFieldRow label="Đường dẫn ảnh Logo (URL)" htmlFor="portal_logo_url" error={validationErrors.portal_logo_url}>
                <input
                  id="portal_logo_url"
                  type="text"
                  value={settings.portal_logo_url || ''}
                  onChange={(e) => handleInputChange('portal_logo_url', e.target.value)}
                  placeholder="https://assets.local/logo.png"
                />
              </SettingsFieldRow>
            </CompactFormGrid>

            <LogoPreview url={settings.portal_logo_url} fallbackText={settings.academy_name} />
          </SettingsSectionCard>

          <SettingsSectionCard
            title="Quy chế phòng thi"
            description="Nội dung hiển thị bắt buộc cho thí sinh đọc và xác nhận cam kết trước giờ thi."
          >
            <SettingsFieldRow
              label="Nội quy / Hướng dẫn phòng thi (Plain text)"
              htmlFor="exam_regulations"
              required={true}
              error={validationErrors.exam_regulations}
            >
              <ExamRegulationsEditor value={settings.exam_regulations} onChange={(val) => handleInputChange('exam_regulations', val)} />
            </SettingsFieldRow>
          </SettingsSectionCard>

          <SettingsSectionCard
            title="Liên hệ & Hỗ trợ kỹ thuật"
            description="Email và số điện thoại đường dây nóng hiển thị cho sinh viên và cán bộ coi thi khi có sự cố."
          >
            <CompactFormGrid>
              <SettingsFieldRow label="Email hỗ trợ" htmlFor="support_email" required={true} error={validationErrors.support_email}>
                <input
                  id="support_email"
                  type="email"
                  value={settings.support_email}
                  onChange={(e) => handleInputChange('support_email', e.target.value)}
                  placeholder="support@academy.edu.vn"
                  required
                />
              </SettingsFieldRow>

              <SettingsFieldRow label="Hotline hỗ trợ kỹ thuật" htmlFor="support_hotline" required={true} error={validationErrors.support_hotline}>
                <input
                  id="support_hotline"
                  type="text"
                  value={settings.support_hotline || ''}
                  onChange={(e) => handleInputChange('support_hotline', e.target.value)}
                  placeholder="0123-456-789"
                />
              </SettingsFieldRow>
            </CompactFormGrid>
          </SettingsSectionCard>

          <SettingsSectionCard
            title="Quy tắc vận hành ca thi (Runtime Rules)"
            description="Cấu hình các tham số phân bổ thời gian và tài nguyên trong phòng thi."
          >
            <CompactFormGrid>
              <SettingsFieldRow
                label="Mở đề trước giờ thi (Phút)"
                htmlFor="exam_start_window_minutes"
                required={true}
                description="Khoảng thời gian mở đề trước khi ca thi chính thức bắt đầu."
                error={validationErrors.exam_start_window_minutes}
              >
                <input
                  id="exam_start_window_minutes"
                  type="number"
                  value={settings.exam_start_window_minutes !== undefined ? settings.exam_start_window_minutes : ''}
                  onChange={(e) => handleInputChange('exam_start_window_minutes', e.target.value === '' ? undefined : Number(e.target.value))}
                  min={0}
                  max={120}
                />
              </SettingsFieldRow>

              <SettingsFieldRow
                label="Thời gian đi trễ tối đa (Phút)"
                htmlFor="late_entry_window_minutes"
                required={true}
                description="Sinh viên đi trễ quá số phút này sẽ không được vào làm bài."
                error={validationErrors.late_entry_window_minutes}
              >
                <input
                  id="late_entry_window_minutes"
                  type="number"
                  value={settings.late_entry_window_minutes !== undefined ? settings.late_entry_window_minutes : ''}
                  onChange={(e) => handleInputChange('late_entry_window_minutes', e.target.value === '' ? undefined : Number(e.target.value))}
                  min={0}
                  max={120}
                />
              </SettingsFieldRow>

              <SettingsFieldRow
                label="Tự động lưu bài thi (Giây)"
                htmlFor="autosave_interval_seconds"
                required={true}
                description="Khoảng thời gian tự động đồng bộ bài thi của sinh viên lên máy chủ."
                error={validationErrors.autosave_interval_seconds}
              >
                <input
                  id="autosave_interval_seconds"
                  type="number"
                  value={settings.autosave_interval_seconds !== undefined ? settings.autosave_interval_seconds : ''}
                  onChange={(e) => handleInputChange('autosave_interval_seconds', e.target.value === '' ? undefined : Number(e.target.value))}
                  min={5}
                  max={120}
                />
              </SettingsFieldRow>
            </CompactFormGrid>
          </SettingsSectionCard>

          <SettingsSectionCard
            title="An toàn & Bảo mật phiên thi"
            description="Cấu hình kiểm tra trạng thái thí sinh và giám sát kết nối."
          >
            <CompactFormGrid columns={1}>
              <SettingsFieldRow
                label="Tần suất gửi tín hiệu duy trì phiên (Heartbeat - giây)"
                htmlFor="session_heartbeat_seconds"
                required={true}
                description="Khoảng thời gian trình duyệt của sinh viên gửi tín hiệu duy trì trạng thái."
                error={validationErrors.session_heartbeat_seconds}
              >
                <input
                  id="session_heartbeat_seconds"
                  type="number"
                  value={settings.session_heartbeat_seconds !== undefined ? settings.session_heartbeat_seconds : ''}
                  onChange={(e) => handleInputChange('session_heartbeat_seconds', e.target.value === '' ? undefined : Number(e.target.value))}
                  min={5}
                  max={300}
                />
              </SettingsFieldRow>

              <label className="settings-checkbox-label" htmlFor="concurrent_login_check">
                <input
                  id="concurrent_login_check"
                  type="checkbox"
                  checked={!!settings.concurrent_login_check}
                  onChange={(e) => handleInputChange('concurrent_login_check', e.target.checked)}
                />
                Ngăn chặn đăng nhập đồng thời trên nhiều thiết bị
              </label>

              <span className="settings-security-note">
                * Chú ý: Các quy tắc an toàn phiên thi cần có sự hỗ trợ thực thi đồng bộ từ phía máy chủ để bảo đảm hiệu quả tối đa.
              </span>
            </CompactFormGrid>
          </SettingsSectionCard>

          <SettingsSectionCard
            title="Phân bổ Giám thị (Proctor Rules)"
            description="Cấu hình quy tắc bố trí cán bộ coi thi cho các phòng máy và ca thi."
          >
            <CompactFormGrid>
              <SettingsFieldRow
                label="Số cán bộ coi thi tối thiểu mỗi phòng"
                htmlFor="min_proctors_per_room"
                required={true}
                error={validationErrors.min_proctors_per_room}
              >
                <input
                  id="min_proctors_per_room"
                  type="number"
                  value={settings.min_proctors_per_room !== undefined ? settings.min_proctors_per_room : ''}
                  onChange={(e) => handleInputChange('min_proctors_per_room', e.target.value === '' ? undefined : Number(e.target.value))}
                  min={1}
                />
              </SettingsFieldRow>

              <SettingsFieldRow
                label="Số ca thi tối đa của giám thị mỗi ngày"
                htmlFor="max_sessions_per_proctor_per_day"
                required={true}
                error={validationErrors.max_sessions_per_proctor_per_day}
              >
                <input
                  id="max_sessions_per_proctor_per_day"
                  type="number"
                  value={settings.max_sessions_per_proctor_per_day !== undefined ? settings.max_sessions_per_proctor_per_day : ''}
                  onChange={(e) => handleInputChange('max_sessions_per_proctor_per_day', e.target.value === '' ? undefined : Number(e.target.value))}
                  min={1}
                />
              </SettingsFieldRow>
            </CompactFormGrid>
          </SettingsSectionCard>

          <SettingsAuditMeta updatedAt={settings.updated_at} updatedBy={settings.updated_by} version={settings.version} />

          <SaveSettingsBar isDirty={isDirty} saving={saving} onReset={handleReset} />
        </form>
      )}
    </CompactPage>
  );
}
