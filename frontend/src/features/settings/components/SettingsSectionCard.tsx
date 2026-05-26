import React from 'react';
import { CompactFormSection } from './CompactFormPrimitives';

interface SettingsSectionCardProps {
  title: string;
  description?: string;
  children: React.ReactNode;
}

export function SettingsSectionCard({ title, description, children }: SettingsSectionCardProps) {
  return <CompactFormSection title={title} description={description}>{children}</CompactFormSection>;
}
