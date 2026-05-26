import { CompactPageHeader } from '../../../shared/components/compact/CompactPageHeader';

export function AdminSurfaceHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return <CompactPageHeader eyebrow={eyebrow} title={title} description={description} />;
}
