import React from 'react';
import { EmptyState } from './EmptyState';

export type ColumnDefinition<T> = {
  key: string;
  header: string;
  render?: (row: T) => React.ReactNode;
  sortable?: boolean;
  align?: 'left' | 'center' | 'right';
  width?: string;
};

export type SortingState = {
  columnKey: string;
  direction: 'asc' | 'desc';
} | null;

export type PaginationState = {
  currentPage: number;
  totalPages: number;
  pageSize: number;
  totalItems: number;
};

type DataTableProps<T> = {
  columns: ColumnDefinition<T>[];
  data: T[];
  loading?: boolean;
  sorting?: SortingState;
  onSort?: (columnKey: string) => void;
  pagination?: PaginationState;
  onPageChange?: (page: number) => void;
  emptyMessage?: string;
  emptyActionLabel?: string;
  onEmptyAction?: () => void;
};

export function DataTable<T>({
  columns,
  data,
  loading = false,
  sorting = null,
  onSort,
  pagination,
  onPageChange,
  emptyMessage = 'Không tìm thấy dữ liệu phù hợp.',
  emptyActionLabel,
  onEmptyAction,
}: DataTableProps<T>) {
  return (
    <div className="table-shell" style={{ position: 'relative' }}>
      {/* Loading overlay */}
      {loading && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(255, 255, 255, 0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 10,
            borderRadius: 'var(--radius-lg)',
          }}
        >
          <div
            style={{
              padding: 'var(--sp-4) var(--sp-6)',
              background: '#fff',
              boxShadow: 'var(--shadow-lg)',
              borderRadius: 'var(--radius-md)',
              fontWeight: 'var(--fw-semibold)',
              color: 'var(--clr-primary-600)',
            }}
          >
            Đang tải dữ liệu...
          </div>
        </div>
      )}

      {/* Scrollable table container */}
      <div className="table-scroll">
        <table className="table table-hover">
          <thead>
            <tr>
              {columns.map((col) => {
                const isSortable = col.sortable && onSort;
                const isSorted = sorting?.columnKey === col.key;
                const alignStyle = col.align ? { textAlign: col.align } : {};

                return (
                  <th
                    key={col.key}
                    style={{
                      cursor: isSortable ? 'pointer' : 'default',
                      userSelect: isSortable ? 'none' : 'auto',
                      width: col.width,
                      ...alignStyle,
                    }}
                    onClick={() => isSortable && onSort(col.key)}
                  >
                    <div
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 'var(--sp-1)',
                      }}
                    >
                      {col.header}
                      {isSortable && (
                        <span style={{ fontSize: '10px', color: isSorted ? 'var(--clr-primary-600)' : 'var(--clr-gray-400)' }}>
                          {isSorted ? (sorting.direction === 'asc' ? '▲' : '▼') : '↕'}
                        </span>
                      )}
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {!loading && data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} style={{ padding: 0 }}>
                  <EmptyState
                    message={emptyMessage}
                    actionLabel={emptyActionLabel}
                    onAction={onEmptyAction}
                  />
                </td>
              </tr>
            ) : (
              data.map((row, idx) => (
                <tr key={idx}>
                  {columns.map((col) => {
                    const alignStyle = col.align ? { textAlign: col.align } : {};
                    return (
                      <td key={col.key} style={alignStyle}>
                        {col.render ? col.render(row) : (row[col.key as keyof T] as React.ReactNode)}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      {pagination && pagination.totalPages > 1 && onPageChange && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: 'var(--sp-3) var(--sp-4)',
            borderTop: '1px solid var(--clr-gray-200)',
            background: 'var(--surface-card)',
            fontSize: 'var(--text-xs)',
            color: 'var(--text-secondary)',
          }}
        >
          <div>
            Hiển thị <strong>{data.length}</strong> dòng (Tổng số: {pagination.totalItems})
          </div>

          <div style={{ display: 'flex', gap: 'var(--sp-1)' }}>
            <button
              type="button"
              className="secondary-button compact-button"
              disabled={pagination.currentPage <= 1}
              onClick={() => onPageChange(pagination.currentPage - 1)}
            >
              Trước
            </button>

            {Array.from({ length: pagination.totalPages }, (_, i) => i + 1).map((p) => {
              const isActive = p === pagination.currentPage;
              return (
                <button
                  key={p}
                  type="button"
                  className={isActive ? 'primary-button compact-button' : 'secondary-button compact-button'}
                  style={isActive ? { background: 'var(--clr-primary-600)', color: '#fff' } : {}}
                  onClick={() => onPageChange(p)}
                >
                  {p}
                </button>
              );
            })}

            <button
              type="button"
              className="secondary-button compact-button"
              disabled={pagination.currentPage >= pagination.totalPages}
              onClick={() => onPageChange(pagination.currentPage + 1)}
            >
              Sau
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
