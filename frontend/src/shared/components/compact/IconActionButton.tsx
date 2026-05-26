import { createContext, useContext, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

export type CompactIconName =
  | 'refresh'
  | 'chevron-left'
  | 'chevron-right'
  | 'edit'
  | 'view'
  | 'check'
  | 'x';

function CompactIcon({ name }: { name: CompactIconName }) {
  switch (name) {
    case 'refresh':
      return (
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M16 3.5v4h-4" />
          <path d="M16 7.5A6.5 6.5 0 1 0 18 12" />
        </svg>
      );
    case 'chevron-left':
      return (
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="m12.5 4.5-5 5 5 5" />
        </svg>
      );
    case 'chevron-right':
      return (
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="m7.5 4.5 5 5-5 5" />
        </svg>
      );
    case 'edit':
      return (
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3.5 16.5h3l8.2-8.2a1.8 1.8 0 0 0-2.5-2.5L4 14v2.5Z" />
          <path d="m10.8 5.2 4 4" />
        </svg>
      );
    case 'view':
      return (
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M1.8 10s3-5 8.2-5 8.2 5 8.2 5-3 5-8.2 5-8.2-5-8.2-5Z" />
          <circle cx="10" cy="10" r="2.2" />
        </svg>
      );
    case 'check':
      return (
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="m4 10 4 4 8-8" />
        </svg>
      );
    case 'x':
      return (
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="m5 5 10 10" />
          <path d="m15 5-10 10" />
        </svg>
      );
    default:
      return null;
  }
}

export function ActionTooltip({ content, children }: { content: string; children: ReactNode }) {
  return (
    <span className="compact-action-tooltip" data-tooltip={content}>
      {children}
    </span>
  );
}

export type ActionGroupMode = 'icon' | 'iconText' | 'text';
export type ActionGroupDensity = 'compact' | 'normal';
type ActionGroupAlign = 'start' | 'end' | 'between';

const ActionGroupModeContext = createContext<ActionGroupMode | null>(null);

export function CompactActionGroup({
  children,
  className,
  mode,
  density = 'compact',
  align = 'start',
}: {
  children: ReactNode;
  className?: string;
  mode: ActionGroupMode;
  density?: ActionGroupDensity;
  align?: ActionGroupAlign;
}) {
  return (
    <ActionGroupModeContext.Provider value={mode}>
      <div
        className={`compact-action-group${className ? ` ${className}` : ''}`}
        data-action-group="true"
        data-action-mode={mode}
        data-action-density={density}
        data-action-align={align}
      >
        {children}
      </div>
    </ActionGroupModeContext.Provider>
  );
}

export function RowActionGroup({ children, className, mode = 'icon', density = 'compact' }: { children: ReactNode; className?: string; mode?: ActionGroupMode; density?: ActionGroupDensity }) {
  return (
    <CompactActionGroup mode={mode} density={density} align="start" className={`row-action-group${className ? ` ${className}` : ''}`}>
      {children}
    </CompactActionGroup>
  );
}

export function ToolbarActionGroup({
  children,
  className,
  mode = 'icon',
  density = 'compact',
  align = 'end',
}: {
  children: ReactNode;
  className?: string;
  mode?: ActionGroupMode;
  density?: ActionGroupDensity;
  align?: ActionGroupAlign;
}) {
  return (
    <CompactActionGroup mode={mode} density={density} align={align} className={`toolbar-action-group${className ? ` ${className}` : ''}`}>
      {children}
    </CompactActionGroup>
  );
}

export function PrimaryActionSlot({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={`primary-action-slot${className ? ` ${className}` : ''}`}>{children}</div>;
}

type VariantClass = 'secondary-button' | 'primary-button' | 'ghost-button';

export function IconActionButton({
  icon,
  label,
  title,
  to,
  showLabel = false,
  className,
  variant = 'secondary-button',
  ...buttonProps
}: {
  icon: CompactIconName;
  label: string;
  title?: string;
  to?: string;
  showLabel?: boolean;
  className?: string;
  variant?: VariantClass;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'>) {
  const groupMode = useContext(ActionGroupModeContext);
  const shouldRenderLabel = groupMode === 'icon' ? false : groupMode === 'iconText' ? true : showLabel;
  const shouldRenderIcon = groupMode === 'text' ? false : true;
  const combinedClassName = `compact-icon-action ${variant} compact-button${shouldRenderLabel ? ' compact-icon-action--with-label' : ''}${className ? ` ${className}` : ''}`;
  const tooltip = title ?? label;

  if (to) {
    return (
      <ActionTooltip content={tooltip}>
        <Link to={to} className={combinedClassName} aria-label={label} title={tooltip}>
          {shouldRenderIcon ? (
            <span className="compact-icon-action__icon">
              <CompactIcon name={icon} />
            </span>
          ) : null}
          {shouldRenderLabel ? <span>{label}</span> : null}
        </Link>
      </ActionTooltip>
    );
  }

  return (
    <ActionTooltip content={tooltip}>
      <button {...buttonProps} type={buttonProps.type ?? 'button'} className={combinedClassName} aria-label={label} title={tooltip}>
        {shouldRenderIcon ? (
          <span className="compact-icon-action__icon">
            <CompactIcon name={icon} />
          </span>
        ) : null}
        {shouldRenderLabel ? <span>{label}</span> : null}
      </button>
    </ActionTooltip>
  );
}
