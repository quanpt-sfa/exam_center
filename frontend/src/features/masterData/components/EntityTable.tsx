import type { MasterDataRow } from '../api/contracts';
import type { EntityColumnConfig } from '../types';
import { useLocale } from '../../../app/locale';
import { resolveDisplayLabel } from '../utils/displayLabel';
import { displayCell, getCellValue } from '../utils/formatters';
import { IconActionButton, RowActionGroup } from '../../../shared/components/compact/IconActionButton';

export function EntityTable({
  columns,
  rows,
  primaryKey,
  loading,
  onEdit,
  onDeactivate,
  getEditDisabled,
  getDeactivateDisabled,
}: {
  columns: EntityColumnConfig[];
  rows: MasterDataRow[];
  primaryKey: string;
  loading: boolean;
  onEdit?: (row: MasterDataRow) => void;
  onDeactivate?: (row: MasterDataRow) => void;
  getEditDisabled?: (row: MasterDataRow) => boolean;
  getDeactivateDisabled?: (row: MasterDataRow) => boolean;
}) {
  const { locale } = useLocale();
  const hasActions = Boolean(onEdit || onDeactivate);

  return (
    <div className="master-data-table-wrap compact-data-table">
      {loading ? (
        <p className="muted">Đang tải...</p>
      ) : (
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key}>{resolveDisplayLabel(column.label, locale)}</th>
              ))}
              {hasActions ? <th>Thao tác</th> : null}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={Math.max(columns.length + (hasActions ? 1 : 0), 1)}>Chưa có dữ liệu.</td>
              </tr>
            ) : (
              rows.map((row, index) => (
                <tr key={String(row[primaryKey] ?? index)}>
                  {columns.map((column) => (
                    <td key={column.key}>{displayCell(getCellValue(row, column.key))}</td>
                  ))}
                  {hasActions ? (
                    <td>
                      <RowActionGroup className="master-data-row-actions master-data-row-actions--compact">
                        {onEdit ? (
                          <IconActionButton
                            icon="edit"
                            label="Sửa"
                            onClick={() => onEdit(row)}
                            disabled={getEditDisabled?.(row)}
                          />
                        ) : null}
                        {onDeactivate ? (
                          <IconActionButton
                            icon="x"
                            label={getDeactivateDisabled?.(row) ? 'Đang xử lý...' : 'Ngừng sử dụng'}
                            onClick={() => onDeactivate(row)}
                            disabled={getDeactivateDisabled?.(row)}
                          />
                        ) : null}
                      </RowActionGroup>
                    </td>
                  ) : null}
                </tr>
              ))
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
