import React from 'react';
import { CompactField } from './CompactFormPrimitives';

interface SettingsFieldRowProps {
  label: string;
  htmlFor: string;
  description?: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
}

export function SettingsFieldRow({ label, htmlFor, description, error, required = false, children }: SettingsFieldRowProps) {
  return (
    <CompactField label={label} htmlFor={htmlFor} description={description} error={error} required={required}>
      {children}
    </CompactField>
  );
}
