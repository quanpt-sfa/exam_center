import type { FormEvent } from 'react';
import { CompactSurface } from '../../../shared/components/compact/CompactSurface';
import { useLocale } from '../../../app/locale';
import type { EntityConfig, EntityFieldConfig, LookupFieldState } from '../types';
import { resolveDisplayLabel } from '../utils/displayLabel';
import { EntityForm } from './EntityForm';

export function EntityCreatePanel({
  entity,
  mode,
  form,
  fieldErrors,
  submitting,
  submitDisabled,
  onSubmit,
  onChange,
  onCancel,
  getOptionsForField,
  getLookupState,
}: {
  entity: EntityConfig;
  mode: 'create' | 'edit';
  form: Record<string, string>;
  fieldErrors: Record<string, string>;
  submitting: boolean;
  submitDisabled: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onChange: (fieldName: string, value: string) => void;
  onCancel?: () => void;
  getOptionsForField: (field: EntityFieldConfig) => Array<{ label: string; value: string }>;
  getLookupState: (field: EntityFieldConfig) => LookupFieldState;
}) {
  const { locale } = useLocale();
  const entityLabel = resolveDisplayLabel(entity.label, locale);

  return (
    <CompactSurface
      className="master-data-create-surface"
      title={mode === 'edit' ? `Cập nhật ${entityLabel.toLowerCase()}` : `Tạo mới ${entityLabel.toLowerCase()}`}
    >
      <form className="master-data-form master-data-form--compact" onSubmit={onSubmit}>
        <EntityForm
          entityKey={entity.key}
          fields={entity.fields}
          form={form}
          fieldErrors={fieldErrors}
          onChange={onChange}
          getOptionsForField={getOptionsForField}
          getLookupState={getLookupState}
        />

        <div className="master-data-form-actions">
          {onCancel ? (
            <button type="button" className="secondary-button compact-button" onClick={onCancel} disabled={submitting}>
              Hủy
            </button>
          ) : null}
          <button className="primary-button compact-button" type="submit" disabled={submitting || submitDisabled} aria-busy={submitting}>
            {submitting ? 'Đang lưu...' : mode === 'edit' ? 'Cập nhật' : 'Lưu'}
          </button>
        </div>
      </form>
    </CompactSurface>
  );
}
