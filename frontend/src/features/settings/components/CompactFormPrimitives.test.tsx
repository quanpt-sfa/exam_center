import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import { CompactField, CompactFormGrid } from './CompactFormPrimitives';

describe('CompactFormPrimitives', () => {
  test('labels and required markers remain accessible without breaking label queries', () => {
    render(
      <form>
        <CompactField
          label="Email hỗ trợ"
          htmlFor="support_email"
          required={true}
          description="Dùng cho thông báo vận hành"
          error="Email không hợp lệ"
        >
          <input id="support_email" type="email" />
        </CompactField>
      </form>
    );

    expect(screen.getByLabelText(/Email hỗ trợ/i)).toBeInTheDocument();
    expect(screen.getByText('Dùng cho thông báo vận hành')).toBeInTheDocument();
    expect(screen.getByText('Email không hợp lệ')).toBeInTheDocument();
    expect(screen.getByText('Email hỗ trợ', { selector: 'label' })).toHaveTextContent('Email hỗ trợ*');
  });

  test('compact form grid renders two-column class and children', () => {
    render(
      <CompactFormGrid>
        <div data-testid="field-a">A</div>
        <div data-testid="field-b">B</div>
      </CompactFormGrid>
    );

    const grid = screen.getByTestId('field-a').parentElement;
    expect(grid).toHaveClass('settings-form-grid');
    expect(grid).toHaveClass('settings-form-grid--2');
    expect(screen.getByTestId('field-a')).toBeInTheDocument();
    expect(screen.getByTestId('field-b')).toBeInTheDocument();
  });
});
