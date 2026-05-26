import React from 'react';

type FilterBarProps = {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  onReset?: () => void;
  children?: React.ReactNode;
};

export function FilterBar({
  searchQuery,
  onSearchChange,
  searchPlaceholder = 'Tìm kiếm...',
  onReset,
  children,
}: FilterBarProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 'var(--sp-3)',
        padding: 'var(--sp-4)',
        background: 'var(--surface-card)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--clr-gray-200)',
        marginBottom: 'var(--sp-4)',
      }}
    >
      {/* Search Input Container */}
      <div style={{ flex: '1 1 240px', position: 'relative' }}>
        <input
          type="search"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder={searchPlaceholder}
          style={{
            width: '100%',
            padding: 'var(--sp-2) var(--sp-3) var(--sp-2) var(--sp-8)',
            border: '1px solid var(--clr-gray-300)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--surface-body)',
            color: 'var(--text-primary)',
            fontSize: 'var(--text-sm)',
          }}
        />
        <span
          style={{
            position: 'absolute',
            left: 'var(--sp-2-5)',
            top: '50%',
            transform: 'translateY(-50%)',
            pointerEvents: 'none',
            fontSize: '14px',
            opacity: 0.6,
          }}
          aria-hidden="true"
        >
          🔍
        </span>
      </div>

      {/* Extra Filters (children) */}
      {children && (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: 'var(--sp-2)',
            flex: '1 1 auto',
          }}
        >
          {children}
        </div>
      )}

      {/* Reset button */}
      {onReset && (
        <button
          type="button"
          className="secondary-button compact-button"
          onClick={onReset}
          style={{
            minWidth: '80px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 'var(--sp-1)',
          }}
        >
          🔄 Làm mới
        </button>
      )}
    </div>
  );
}
