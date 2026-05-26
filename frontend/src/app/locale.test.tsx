import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, test } from 'vitest';
import { AppLocaleProvider, resolveLocalizedText, useLocale } from './locale';

function LocaleProbe() {
  const { locale } = useLocale();
  return <span data-testid="locale-probe">{locale}</span>;
}

describe('app locale contract', () => {
  beforeEach(() => {
    window.localStorage.removeItem('locale');
    window.localStorage.removeItem('language');
    window.localStorage.removeItem('lang');
    window.localStorage.removeItem('ui_locale');
  });

  test('defaults to vi when no locale is provided', () => {
    render(
      <AppLocaleProvider>
        <LocaleProbe />
      </AppLocaleProvider>
    );

    expect(screen.getByTestId('locale-probe')).toHaveTextContent('vi');
  });

  test('resolves localized text to Vietnamese by default', () => {
    const label = resolveLocalizedText({ labelVi: 'Tên khoa', labelEn: 'Department name' }, 'vi');

    expect(label).toBe('Tên khoa');
  });

  test('supports deterministic english selection in tests', () => {
    render(
      <AppLocaleProvider initialLocale="en">
        <LocaleProbe />
      </AppLocaleProvider>
    );

    expect(screen.getByTestId('locale-probe')).toHaveTextContent('en');
    expect(resolveLocalizedText({ labelVi: 'Tên khoa', labelEn: 'Department name' }, 'en')).toBe('Department name');
  });
});
