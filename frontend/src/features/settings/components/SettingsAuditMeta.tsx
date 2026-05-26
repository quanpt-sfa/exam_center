import { CompactAuditMetadata } from './CompactFormPrimitives';

interface SettingsAuditMetaProps {
  updatedAt?: string;
  updatedBy?: number | string | null;
  version?: number;
}

export function SettingsAuditMeta({ updatedAt, updatedBy, version }: SettingsAuditMetaProps) {
  return <CompactAuditMetadata updatedAt={updatedAt} updatedBy={updatedBy} version={version} />;
}
