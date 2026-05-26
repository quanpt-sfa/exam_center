import React from 'react';

type EmptyStateProps = {
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  icon?: string;
};

export function EmptyState({ message, actionLabel, onAction, icon = '📁' }: EmptyStateProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--sp-8) var(--sp-4)',
        textAlign: 'center',
        background: 'var(--surface-body)',
        borderRadius: 'var(--radius-lg)',
        border: '1px dashed var(--clr-gray-300)',
        margin: 'var(--sp-4)',
      }}
    >
      <span
        style={{
          fontSize: 'var(--text-3xl)',
          marginBottom: 'var(--sp-3)',
          display: 'block',
          opacity: 0.8,
        }}
        aria-hidden="true"
      >
        {icon}
      </span>
      <p
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--text-secondary)',
          margin: '0 0 var(--sp-4) 0',
          maxWidth: '380px',
        }}
      >
        {message}
      </p>
      {actionLabel && onAction && (
        <button
          type="button"
          className="primary-button"
          onClick={onAction}
          style={{ minWidth: '120px' }}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
