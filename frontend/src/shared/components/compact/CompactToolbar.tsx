import type { HTMLAttributes, ReactNode } from 'react';

export function CompactToolbar({
  children,
  className = '',
  ...rest
}: {
  children: ReactNode;
  className?: string;
} & HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`compact-toolbar${className ? ` ${className}` : ''}`.trim()} {...rest}>
      {children}
    </div>
  );
}
