import type { HTMLAttributes, ReactNode } from 'react';

export function CompactPage({
  children,
  className = '',
  ...rest
}: {
  children: ReactNode;
  className?: string;
} & HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`compact-page${className ? ` ${className}` : ''}`.trim()} {...rest}>
      {children}
    </div>
  );
}
