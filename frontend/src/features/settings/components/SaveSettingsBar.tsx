import { CompactFormActions } from './CompactFormPrimitives';

interface SaveSettingsBarProps {
  isDirty: boolean;
  saving: boolean;
  onReset: () => void;
}

export function SaveSettingsBar({ isDirty, saving, onReset }: SaveSettingsBarProps) {
  return <CompactFormActions isDirty={isDirty} saving={saving} onReset={onReset} />;
}
