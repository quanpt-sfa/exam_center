import type { HTMLAttributes, ReactNode } from 'react';

export function CompactSurface({
  children,
  title,
  description,
  actions,
  tight = false,
  className = '',
  ...rest
}: {
  children: ReactNode;
  title?: string;
  description?: string;
  actions?: ReactNode;
  tight?: boolean;
  className?: string;
} & HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={`compact-surface${tight ? ' compact-surface--tight' : ''}${className ? ` ${className}` : ''}`.trim()}
      {...rest}
    >
      {title || description || actions ? (
        <div className="compact-surface__header">
          <div>
            {title ? <h3>{title}</h3> : null}
            {description ? <p className="muted">{description}</p> : null}
          </div>
          {actions ? <div>{actions}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}
