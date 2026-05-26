import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, test } from 'vitest';
import { ExamSetupLandingPage } from './ExamSetupLandingPage';

describe('ExamSetupLandingPage', () => {
  test('renders workflow links without mixed operational content', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ExamSetupLandingPage />
      </MemoryRouter>
    );

    expect(screen.getByTestId('exam-setup-landing-page')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Thiết lập trước khi thi' })).toBeInTheDocument();
    const workflowLinks = screen.getAllByRole('link', { name: 'Mở workflow' });
    expect(workflowLinks).toHaveLength(2);
    expect(workflowLinks[0]).toHaveAttribute('href', '/admin/exam-setup/authoring');
    expect(workflowLinks[1]).toHaveAttribute('href', '/admin/exam-setup/delivery');
    expect(screen.queryByText(/Worker process heartbeat/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Delivery runtime/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Submission autosave\/seal\/dispatch/i)).not.toBeInTheDocument();
  });
});