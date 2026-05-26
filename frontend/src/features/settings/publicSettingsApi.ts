import { httpRequest } from '../../shared/api/httpClient';
import { ApiEnvelope } from '../../shared/api/apiEnvelope';
import { PublicSystemSettings } from './settingsApi';
import { DEFAULT_PUBLIC_SETTINGS } from './settingsDefaults';

export async function loadPublicSettings(): Promise<ApiEnvelope<PublicSystemSettings>> {
  const isMock = localStorage.getItem('use_mock_settings_api') === 'true';

  if (isMock) {
    const mockSaved = localStorage.getItem('mock_admin_runtime_settings');
    if (mockSaved) {
      try {
        const parsed = JSON.parse(mockSaved);
        return {
          ok: true,
          success: true,
          data: {
            academy_name: parsed.academy_name,
            portal_logo_url: parsed.portal_logo_url,
            exam_regulations: parsed.exam_regulations,
            support_email: parsed.support_email,
            support_hotline: parsed.support_hotline,
          },
          message: null,
          error: null,
        };
      } catch {
        // ignore
      }
    }

    return {
      ok: true,
      success: true,
      data: DEFAULT_PUBLIC_SETTINGS,
      message: null,
      error: null,
    };
  }

  // Non-mock mode: call the live endpoint
  const response = await httpRequest<PublicSystemSettings>('/system/settings/public', {
    method: 'GET',
  });

  if (response && response.ok) {
    return response;
  }

  // Return API error directly; do not read mock_admin_runtime_settings,
  // do not let stale mock data affect public UI.
  return {
    ok: false,
    success: false,
    data: null,
    error: {
      code: response && !response.ok && response.error ? response.error.code : 'request_failed',
      message: response && !response.ok && response.error ? response.error.message : 'Cannot load public settings from live backend',
    },
    message: null,
  };
}
