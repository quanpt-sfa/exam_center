import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import { ExamTakerIdentityPanel } from './ExamTakerIdentityPanel';
import type { StudentCandidateProfile } from './types';

describe('ExamTakerIdentityPanel', () => {
  test('renders student photo, full name, and student code when provided', () => {
    const candidate: StudentCandidateProfile = {
      student_id: 1,
      full_name: 'Nguyễn Văn A',
      student_code: 'B22DCCN001',
      photo_url: 'https://assets.local/photo.jpg',
    };

    render(<ExamTakerIdentityPanel candidate={candidate} />);

    expect(screen.getByText('Nguyễn Văn A')).toBeInTheDocument();
    expect(screen.getByText('B22DCCN001')).toBeInTheDocument();
    const img = screen.getByAltText('Nguyễn Văn A');
    expect(img).toHaveAttribute('src', 'https://assets.local/photo.jpg');
  });

  test('renders initials as fallback when photo_url is not provided', () => {
    const candidate: StudentCandidateProfile = {
      student_id: 2,
      full_name: 'Trần Thị B',
      student_code: 'B22DCCN002',
    };

    render(<ExamTakerIdentityPanel candidate={candidate} />);

    expect(screen.getByText('Trần Thị B')).toBeInTheDocument();
    expect(screen.getByText('B22DCCN002')).toBeInTheDocument();
    expect(screen.getByLabelText('Ảnh thay thế của Trần Thị B')).toHaveTextContent('TB');
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  test('renders initials fallback when image fails to load', () => {
    const candidate: StudentCandidateProfile = {
      student_id: 3,
      full_name: 'Lê Văn C',
      student_code: 'B22DCCN003',
      photo_url: 'https://assets.local/broken-image.jpg',
    };

    render(<ExamTakerIdentityPanel candidate={candidate} />);

    const img = screen.getByAltText('Lê Văn C');
    fireEvent.error(img);

    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Ảnh thay thế của Lê Văn C')).toHaveTextContent('LC');
  });

  test('renders placeholder panel when candidate is not provided', () => {
    render(<ExamTakerIdentityPanel candidate={null} />);

    expect(screen.getByText('Chưa có dữ liệu định danh')).toBeInTheDocument();
    expect(screen.getByText(/Backend chưa cung cấp họ tên hoặc mã sinh viên/i)).toBeInTheDocument();
  });
});
