import { useEffect, useState, type ReactNode } from 'react';
import { CompactSurface } from '../../../shared/components/compact/CompactSurface';
import { CompactToolbar } from '../../../shared/components/compact/CompactToolbar';
import { IconActionButton, RowActionGroup } from '../../../shared/components/compact/IconActionButton';
import type { MasterDataRow, Pagination } from '../api/contracts';
import type { EntityConfig } from '../types';
import { resolveDisplayLabel } from '../utils/displayLabel';
import { EntityTable } from './EntityTable';
import { useLocale } from '../../../app/locale';

export function EntityListPanel({
  entity,
  rows,
  pagination,
  loading,
  error,
  message,
  listParams,
  onQueryChange,
  onStatusChange,
  onPageChange,
  onPageSizeChange,
  onReload,
  onEdit,
  onDeactivate,
  getEditDisabled,
  getDeactivateDisabled,
  emptyState,
}: {
  entity: EntityConfig;
  rows: MasterDataRow[];
  pagination?: Pagination;
  loading: boolean;
  error: string | null;
  message: string | null;
  listParams: { query?: string; status?: string; page: number; page_size: number };
  onQueryChange: (query: string) => void;
  onStatusChange: (status: string) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onReload: () => void;
  onEdit?: (row: MasterDataRow) => void;
  onDeactivate?: (row: MasterDataRow) => void;
  getEditDisabled?: (row: MasterDataRow) => boolean;
  getDeactivateDisabled?: (row: MasterDataRow) => boolean;
  emptyState?: ReactNode;
}) {
  const { locale } = useLocale();
  const [draftQuery, setDraftQuery] = useState(listParams.query ?? '');
  const [draftStatus, setDraftStatus] = useState(listParams.status ?? '');

  useEffect(() => {
    setDraftQuery(listParams.query ?? '');
    setDraftStatus(listParams.status ?? '');
  }, [entity.key, listParams.query, listParams.status]);

  const totalItems = pagination?.total;
  const totalPages = pagination?.total_pages;
  const canGoPrevious = pagination?.has_previous ?? listParams.page > 1;
  const canGoNext = pagination?.has_next ?? (totalPages != null ? listParams.page < totalPages : rows.length >= listParams.page_size);
  const entityLabel = resolveDisplayLabel(entity.label, locale);
  const entityDescription = resolveDisplayLabel(entity.description, locale);

  return (
    <section className="master-data-workspace compact-page compact-page--flush">
      <CompactSurface
        className="master-data-list-surface"
        title={entityLabel}
        description={entityDescription}
        actions={
          <IconActionButton icon="refresh" label="Tải lại" onClick={onReload} />
        }
      >
        {entity.listFeatures.supportsQuery || entity.listFeatures.supportsStatusFilter || entity.listFeatures.supportsPagination ? (
          <CompactToolbar className="master-data-list-controls">
            {entity.listFeatures.supportsQuery ? (
              <label>
                Tìm kiếm
                <input value={draftQuery} onChange={(event) => setDraftQuery(event.target.value)} placeholder="Ma, ten, email..." />
              </label>
            ) : null}
            {entity.listFeatures.supportsStatusFilter ? (
              <label>
                Trạng thái
                <select value={draftStatus} onChange={(event) => setDraftStatus(event.target.value)}>
                  <option value="">Tất cả</option>
                  {(entity.listFeatures.statusOptions ?? []).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {entity.listFeatures.supportsPagination ? (
              <label>
                Số dòng/trang
                <select value={String(listParams.page_size)} onChange={(event) => onPageSizeChange(Number(event.target.value))}>
                  {(entity.listFeatures.pageSizeOptions ?? [entity.listFeatures.defaultPageSize]).map((size) => (
                    <option key={size} value={size}>
                      {size}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {entity.listFeatures.supportsQuery || entity.listFeatures.supportsStatusFilter ? (
              <button
                type="button"
                className="primary-button compact-button"
                onClick={() => {
                  onQueryChange(draftQuery);
                  onStatusChange(draftStatus);
                }}
              >
                Áp dụng
              </button>
            ) : null}
          </CompactToolbar>
        ) : null}

        {emptyState}

        {error ? <p className="form-error">{error}</p> : null}
        {message ? <p className="success-message">{message}</p> : null}

        <EntityTable
          columns={entity.columns}
          rows={rows}
          primaryKey={entity.primaryKey}
          loading={loading}
          onEdit={onEdit}
          onDeactivate={onDeactivate}
          getEditDisabled={getEditDisabled}
          getDeactivateDisabled={getDeactivateDisabled}
        />

        {entity.listFeatures.supportsPagination ? (
          <div className="master-data-pagination">
            <span className="muted">
              Trang {listParams.page}
              {totalPages != null ? ` / ${totalPages}` : ''}
              {totalItems != null ? ` - ${totalItems} bản ghi` : ''}
            </span>
            <RowActionGroup className="master-data-row-actions master-data-row-actions--compact">
              <IconActionButton icon="chevron-left" label="Trước" onClick={() => onPageChange(listParams.page - 1)} disabled={!canGoPrevious} />
              <IconActionButton icon="chevron-right" label="Sau" onClick={() => onPageChange(listParams.page + 1)} disabled={!canGoNext} />
            </RowActionGroup>
          </div>
        ) : null}
      </CompactSurface>
    </section>
  );
}
