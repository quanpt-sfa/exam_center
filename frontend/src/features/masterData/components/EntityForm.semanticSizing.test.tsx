import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';
import { AppLocaleProvider, type Locale } from '../../../app/locale';
import { EntityForm } from './EntityForm';
import type { EntityFieldConfig, LookupFieldState } from '../types';

const defaultLookupState: LookupFieldState = {
  disabled: false,
  loading: false,
  error: null,
  showManualFallback: false,
};

function renderForm(
  fields: EntityFieldConfig[],
  form: Record<string, string>,
  fieldErrors: Record<string, string> = {},
  locale: Locale = 'vi'
) {
  const onChange = vi.fn();

  render(
    <AppLocaleProvider initialLocale={locale}>
      <EntityForm
        entityKey="departments"
        fields={fields}
        form={form}
        fieldErrors={fieldErrors}
        onChange={onChange}
        getOptionsForField={() => []}
        getLookupState={() => defaultLookupState}
      />
    </AppLocaleProvider>
  );

  return { onChange };
}

describe('EntityForm semantic sizing', () => {
  test('applies field data attributes and span class from explicit metadata', () => {
    const fields: EntityFieldConfig[] = [{ name: 'department_code', label: 'Mã đơn vị', fieldKind: 'code', fieldSize: 'sm' }];

    renderForm(fields, { department_code: '' });

    const input = screen.getByLabelText('Mã đơn vị');
    const wrapper = input.closest('div');

    expect(wrapper).toHaveClass('master-data-field', 'field-span-sm');
    expect(wrapper).toHaveAttribute('data-field-kind', 'code');
    expect(wrapper).toHaveAttribute('data-field-size', 'sm');
    expect(wrapper).toHaveAttribute('data-grid-span', '3');
    expect(input).toHaveClass('master-data-control', 'master-data-control--sm');
  });

  test('renders only Vietnamese label when vi/en label config is provided', () => {
    const fields: EntityFieldConfig[] = [
      {
        name: 'department_name',
        label: { labelVi: 'Tên khoa', labelEn: 'Department name' },
        fieldKind: 'longName',
      },
    ];

    renderForm(fields, { department_name: '' });

    expect(screen.getByLabelText('Tên khoa')).toBeInTheDocument();
    expect(screen.queryByText('Department name')).not.toBeInTheDocument();
  });

  test('renders only English label when locale override is en', () => {
    const fields: EntityFieldConfig[] = [
      {
        name: 'department_name',
        label: { labelVi: 'Tên khoa', labelEn: 'Department name' },
        fieldKind: 'longName',
      },
    ];

    renderForm(fields, { department_name: '' }, {}, 'en');

    expect(screen.getByLabelText('Department name')).toBeInTheDocument();
    expect(screen.queryByText('Tên khoa')).not.toBeInTheDocument();
  });

  test('applies lg control class to long-name fields instead of full-width control class', () => {
    const fields: EntityFieldConfig[] = [{ name: 'full_name', label: 'Họ và tên', fieldKind: 'longName' }];

    renderForm(fields, { full_name: '' });

    const input = screen.getByLabelText('Họ và tên');
    const wrapper = input.closest('div');
    expect(wrapper).toHaveAttribute('data-field-size', 'lg');
    expect(input).toHaveClass('master-data-control', 'master-data-control--lg');
    expect(input).not.toHaveClass('master-data-control--full');
  });

  test('keeps aria-describedby chain for helper and validation error', () => {
    const fields: EntityFieldConfig[] = [
      {
        name: 'term_id',
        label: 'ID học kỳ',
        type: 'number',
        helperText: 'Nhập ID hiện có trong hệ thống.',
        fieldKind: 'id',
        fieldSize: 'sm',
      },
    ];

    renderForm(fields, { term_id: '' }, { term_id: 'Trường bắt buộc' });

    const input = screen.getByLabelText('ID học kỳ');
    expect(input).toHaveAttribute('aria-describedby', 'departments-term_id-helper departments-term_id-error');
    expect(screen.getByText('Nhập ID hiện có trong hệ thống.')).toBeInTheDocument();
    expect(screen.getByText('Trường bắt buộc')).toBeInTheDocument();
  });

  test('renders textarea when multiline metadata is set and preserves onChange payload', () => {
    const fields: EntityFieldConfig[] = [
      {
        name: 'department_description',
        label: 'Mô tả đơn vị',
        multiline: true,
        minRows: 4,
        fieldKind: 'description',
      },
    ];

    const { onChange } = renderForm(fields, { department_description: '' });

    const textarea = screen.getByLabelText('Mô tả đơn vị');
    expect(textarea.tagName).toBe('TEXTAREA');
    expect(textarea).toHaveAttribute('rows', '4');
    expect(textarea).toHaveClass('master-data-control', 'master-data-control--full');

    fireEvent.change(textarea, { target: { value: 'Mô tả mới' } });
    expect(onChange).toHaveBeenCalledWith('department_description', 'Mô tả mới');
  });
});
