import { resolveLocalizedText, type Locale } from '../../../app/locale';
import type { DisplayLabelConfig } from '../types';

export function resolveDisplayLabel(labelConfig: DisplayLabelConfig, locale?: Locale): string {
  return resolveLocalizedText(labelConfig, locale);
}
