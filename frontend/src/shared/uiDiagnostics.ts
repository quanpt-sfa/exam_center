export const UI_API_DIAGNOSTICS_FLAG = 'exam_sys_ui_debug_api_status';

export function isUiApiDiagnosticsEnabled(): boolean {
  if (import.meta.env.MODE === 'test') {
    return false;
  }

  if (import.meta.env.DEV) {
    return true;
  }

  if (typeof window === 'undefined') {
    return false;
  }

  return window.localStorage.getItem(UI_API_DIAGNOSTICS_FLAG) === 'true';
}