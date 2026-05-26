import { useEffect, useState } from 'react';
import { loadPublicSettings } from './publicSettingsApi';
import { PublicSystemSettings } from './settingsApi';
import { DEFAULT_PUBLIC_SETTINGS } from './settingsDefaults';

export function usePublicSettings() {
  const [settings, setSettings] = useState<PublicSystemSettings>(DEFAULT_PUBLIC_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function fetchPublicSettings() {
      setLoading(true);
      setError(null);
      const response = await loadPublicSettings();
      if (!active) return;
      setLoading(false);
      if (response.ok) {
        setSettings(response.data);
      } else {
        // Fallback is already handled by publicSettingsApi, but double guard here:
        setSettings(DEFAULT_PUBLIC_SETTINGS);
        setError(response.error?.message || 'Cannot load public settings');
      }
    }
    void fetchPublicSettings();
    return () => {
      active = false;
    };
  }, []);

  return { settings, loading, error };
}
