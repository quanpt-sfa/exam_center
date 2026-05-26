import { httpRequest } from '../../shared/api/httpClient';
import { ApiEnvelope } from '../../shared/api/apiEnvelope';

export interface PublicSystemSettings {
  academy_name: string;
  portal_logo_url: string | null;
  exam_regulations: string;
  support_email: string;
  support_hotline: string;
}

export interface AdminRuntimeSettings extends PublicSystemSettings {
  session_heartbeat_seconds: number;
  concurrent_login_check: boolean;
  autosave_interval_seconds: number;
  exam_start_window_minutes: number;
  late_entry_window_minutes: number;
  min_proctors_per_room: number;
  max_sessions_per_proctor_per_day: number;
  updated_at: string;
  updated_by: number | null;
  version: number;
}

type AdminSettingsUpdatePayload = Omit<AdminRuntimeSettings, 'updated_at' | 'updated_by'>;

function toAdminSettingsUpdatePayload(data: AdminRuntimeSettings): AdminSettingsUpdatePayload {
  const { updated_at: _updatedAt, updated_by: _updatedBy, ...payload } = data;
  return payload;
}

// Memory/localStorage mock state for running without backend API
const LOCAL_STORAGE_KEY = 'mock_admin_runtime_settings';

function getMockSettings(): AdminRuntimeSettings {
  const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
  if (saved) {
    try {
      return JSON.parse(saved);
    } catch {
      // ignore
    }
  }
  return {
    academy_name: 'Học viện Công nghệ Bưu chính Viễn thông',
    portal_logo_url: null,
    exam_regulations: `1. Thí sinh phải có mặt tại phòng thi trước giờ bắt đầu làm bài ít nhất 15 phút.
2. Thí sinh xuất trình Thẻ sinh viên hoặc giấy tờ tùy thân có ảnh khi cán bộ coi thi yêu cầu.
3. Tuyệt đối không mang tài liệu, điện thoại di động, thiết bị thông minh hoặc các vật dụng cấm vào phòng thi.
4. Mọi hành vi gian lận sẽ bị xử lý kỷ luật đình chỉ thi ngay lập tức.`,
    support_email: 'support@academy.edu.vn',
    support_hotline: '0123-456-789',
    session_heartbeat_seconds: 30,
    concurrent_login_check: true,
    autosave_interval_seconds: 10,
    exam_start_window_minutes: 15,
    late_entry_window_minutes: 10,
    min_proctors_per_room: 1,
    max_sessions_per_proctor_per_day: 3,
    updated_at: new Date().toISOString(),
    updated_by: 99,
    version: 1,
  };
}

function saveMockSettings(settings: AdminRuntimeSettings) {
  localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(settings));
}

export function isMockModeEnabled(): boolean {
  return localStorage.getItem('use_mock_settings_api') === 'true';
}

export async function loadSystemSettings(): Promise<ApiEnvelope<AdminRuntimeSettings>> {
  if (isMockModeEnabled()) {
    return {
      ok: true,
      success: true,
      data: getMockSettings(),
      message: null,
      error: null,
    };
  }

  return await httpRequest<AdminRuntimeSettings>('/admin/system/settings', {
    method: 'GET',
  });
}

export async function updateSystemSettings(data: AdminRuntimeSettings): Promise<ApiEnvelope<AdminRuntimeSettings>> {
  if (isMockModeEnabled()) {
    const current = getMockSettings();
    if (current.version !== undefined && data.version !== undefined && current.version > data.version) {
      // Concurrency conflict error mock simulation
      return {
        ok: false,
        success: false,
        data: current,
        message: 'Conflict',
        error: {
          code: 'concurrency_conflict',
          message: 'Cấu hình đã bị thay đổi bởi quản trị viên khác. Vui lòng tải lại trước khi lưu.',
        },
      };
    }

    const updated: AdminRuntimeSettings = {
      ...data,
      version: (data.version || 0) + 1,
      updated_at: new Date().toISOString(),
      updated_by: 99,
    };
    saveMockSettings(updated);

    return {
      ok: true,
      success: true,
      data: updated,
      message: 'Updated successfully',
      error: null,
    };
  }

  return await httpRequest<AdminRuntimeSettings>('/admin/system/settings', {
    method: 'PUT',
    body: JSON.stringify(toAdminSettingsUpdatePayload(data)),
  });
}


