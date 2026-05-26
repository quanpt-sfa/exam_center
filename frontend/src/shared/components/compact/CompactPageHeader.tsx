import type { ReactNode } from 'react';

export function CompactPageHeader({
  eyebrow,
  title,
  description,
  secondaryActions,
  primaryActions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  secondaryActions?: ReactNode;
  primaryActions?: ReactNode;
}) {
  return (
    <section className="compact-page-header">
      <div className="compact-page-header__meta">
        {eyebrow ? <p className="eyebrow compact-page-header__eyebrow">{eyebrow}</p> : null}
        <h2 className="compact-page-header__title">{title}</h2>
        {description ? <p className="compact-page-header__description">{description}</p> : null}
      </div>
      {secondaryActions ? <div className="compact-page-header__secondary">{secondaryActions}</div> : null}
      {primaryActions ? <div className="compact-page-header__actions">{primaryActions}</div> : null}
    </section>
  );
}
