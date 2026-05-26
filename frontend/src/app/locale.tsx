import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

export type Locale = 'vi' | 'en';

export type LocalizedTextConfig =
  | string
  | {
      vi?: string;
      en?: string;
      label?: string;
      labelVi?: string;
      labelEn?: string;
      titleVi?: string;
      titleEn?: string;
      descriptionVi?: string;
      descriptionEn?: string;
      labels?: {
        vi?: string;
        en?: string;
      };
    };

const STORAGE_KEYS = ['locale', 'language', 'lang', 'ui_locale'] as const;

type LocaleContextValue = {
  locale: Locale;
  setLocale: (nextLocale: Locale) => void;
};

function isLocale(value: string | null | undefined): value is Locale {
  return value === 'vi' || value === 'en';
}

export function readStoredLocale(defaultLocale: Locale = 'vi'): Locale {
  if (typeof window === 'undefined') {
    return defaultLocale;
  }

  for (const key of STORAGE_KEYS) {
    const value = window.localStorage.getItem(key);
    if (isLocale(value)) {
      return value;
    }
  }

  return defaultLocale;
}

export function writeStoredLocale(locale: Locale): void {
  if (typeof window === 'undefined') {
    return;
  }

  for (const key of STORAGE_KEYS) {
    window.localStorage.setItem(key, locale);
  }
}

let activeLocale: Locale = 'vi';

export function getActiveLocale(defaultLocale: Locale = 'vi'): Locale {
  return activeLocale || defaultLocale;
}

function pickLocalizedValue(config: Exclude<LocalizedTextConfig, string>, locale: Locale): string {
  const preferred =
    locale === 'en'
      ? config.en ?? config.labels?.en ?? config.labelEn ?? config.titleEn ?? config.descriptionEn
      : config.vi ?? config.labels?.vi ?? config.labelVi ?? config.titleVi ?? config.descriptionVi;

  if (preferred && preferred.trim() !== '') {
    return preferred;
  }

  const fallback =
    locale === 'en'
      ? config.vi ?? config.labels?.vi ?? config.labelVi ?? config.titleVi ?? config.descriptionVi
      : config.en ?? config.labels?.en ?? config.labelEn ?? config.titleEn ?? config.descriptionEn;

  if (fallback && fallback.trim() !== '') {
    return fallback;
  }

  return config.label?.trim() ?? '';
}

export function resolveLocalizedText(config: LocalizedTextConfig, locale: Locale = getActiveLocale('vi')): string {
  if (typeof config === 'string') {
    return config;
  }

  return pickLocalizedValue(config, locale);
}

const AppLocaleContext = createContext<LocaleContextValue>({
  locale: 'vi',
  setLocale: () => undefined,
});

export function AppLocaleProvider({ children, initialLocale }: { children: ReactNode; initialLocale?: Locale }) {
  const [locale, setLocale] = useState<Locale>(() => initialLocale ?? readStoredLocale('vi'));

  useEffect(() => {
    activeLocale = locale;
    writeStoredLocale(locale);
  }, [locale]);

  const value = useMemo(
    () => ({
      locale,
      setLocale,
    }),
    [locale]
  );

  return <AppLocaleContext.Provider value={value}>{children}</AppLocaleContext.Provider>;
}

export function useLocale(): LocaleContextValue {
  return useContext(AppLocaleContext);
}
