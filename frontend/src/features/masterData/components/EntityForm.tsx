import type { EntityFieldConfig, LookupFieldState } from '../types';
import { resolveDisplayLabel } from '../utils/displayLabel';
import { resolveMasterDataFieldLayout } from '../utils/fieldLayout';
import { useLocale } from '../../../app/locale';

export function EntityForm({
  entityKey,
  fields,
  form,
  fieldErrors,
  onChange,
  getOptionsForField,
  getLookupState,
}: {
  entityKey: string;
  fields: EntityFieldConfig[];
  form: Record<string, string>;
  fieldErrors: Record<string, string>;
  onChange: (fieldName: string, value: string) => void;
  getOptionsForField: (field: EntityFieldConfig) => Array<{ label: string; value: string }>;
  getLookupState: (field: EntityFieldConfig) => LookupFieldState;
}) {
  const { locale } = useLocale();
  return (
    <>
      {fields.map((field) => {
        const options = getOptionsForField(field);
        const lookupState = getLookupState(field);
        const showFallbackInput = field.type === 'select' && lookupState.showManualFallback;
        const currentValue = String(form[field.name] ?? '');
        const allowsSyntheticLookupValue =
          field.type === 'select' && field.allowManualLookupFallback === true && field.valueType === 'number' && currentValue.trim() !== '';
        const selectOptions =
          allowsSyntheticLookupValue && !options.some((option) => option.value === currentValue)
            ? [{ value: currentValue, label: `ID hiện có: ${currentValue}` }, ...options]
            : options;
        const helperText =
          field.helperText ??
          (showFallbackInput || (field.valueType === 'number' && field.name.endsWith('_id') && field.type !== 'select')
            ? 'Nhập ID hiện có trong hệ thống.'
            : undefined);
        const helperId = helperText ? `${entityKey}-${field.name}-helper` : undefined;
        const errorId = fieldErrors[field.name] ? `${entityKey}-${field.name}-error` : undefined;
        const describedBy = [helperId, errorId].filter(Boolean).join(' ') || undefined;
        const layout = resolveMasterDataFieldLayout(field, field.name);
        const fieldId = `${entityKey}-${field.name}`;
        const canRenderTextarea = layout.multiline && field.type !== 'select' && field.type !== 'number' && field.type !== 'date';
        const controlClassName = `master-data-control master-data-control--${layout.fieldSize}`;
        const displayLabel = resolveDisplayLabel(field.label, locale) || field.name;
        return (
          <div key={field.name} className={layout.className} {...layout.dataAttributes}>
            <label htmlFor={fieldId}>{displayLabel}</label>
            {field.type === 'select' && !showFallbackInput ? (
              <select
                id={fieldId}
                className={controlClassName}
                value={form[field.name] ?? ''}
                required={field.required}
                disabled={lookupState.disabled}
                aria-describedby={describedBy}
                onChange={(event) => onChange(field.name, event.target.value)}
              >
                <option value="">{lookupState.loading ? 'Đang tải...' : lookupState.error ? 'Không tải được danh mục' : 'Chọn'}</option>
                {selectOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : canRenderTextarea ? (
              <textarea
                id={fieldId}
                className={controlClassName}
                value={form[field.name] ?? ''}
                required={field.required}
                rows={field.minRows ?? 3}
                aria-describedby={describedBy}
                placeholder={field.placeholder}
                onChange={(event) => onChange(field.name, event.target.value)}
              />
            ) : (
              <input
                id={fieldId}
                className={controlClassName}
                type={field.type === 'select' ? 'number' : field.type ?? 'text'}
                value={form[field.name] ?? ''}
                required={field.required}
                min={field.min}
                max={field.max}
                step={field.integer ? 1 : undefined}
                placeholder={field.placeholder}
                inputMode={layout.inputMode}
                aria-describedby={describedBy}
                onChange={(event) => onChange(field.name, event.target.value)}
              />
            )}
            {helperText ? (
              <span id={helperId} className="muted">
                {helperText}
              </span>
            ) : null}
            {lookupState.error ? (
              <span id={`${entityKey}-${field.name}-lookup-error`} className="form-error">
                {lookupState.error}
              </span>
            ) : null}
            {fieldErrors[field.name] ? (
              <span id={errorId} className="form-error">
                {fieldErrors[field.name]}
              </span>
            ) : null}
          </div>
        );
      })}
    </>
  );
}