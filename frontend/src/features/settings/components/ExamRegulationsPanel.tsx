import { useState } from 'react';

interface ExamRegulationsPanelProps {
  regulationsText: string;
  loading?: boolean;
  error?: string | null;
  onAgreeChange?: (agreed: boolean) => void;
  showAgreementCheckbox?: boolean;
}

export function ExamRegulationsPanel({
  regulationsText,
  loading,
  error,
  onAgreeChange,
  showAgreementCheckbox = false,
}: ExamRegulationsPanelProps) {
  const [agreed, setAgreed] = useState(false);

  const handleCheckboxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.checked;
    setAgreed(val);
    if (onAgreeChange) {
      onAgreeChange(val);
    }
  };

  if (loading) {
    return <p className="muted">Đang tải quy chế phòng thi...</p>;
  }

  if (error) {
    return (
      <div className="form-error" role="alert" style={{ padding: 'var(--sp-3)' }}>
        Không thể tải quy chế phòng thi. Lỗi: {error}
      </div>
    );
  }

  return (
    <div className="exam-regulations-panel" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-3)' }}>
      <div
        style={{
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--border-radius-md)',
          padding: 'var(--sp-4)',
          backgroundColor: 'var(--bg-card-header)',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          fontSize: '0.9rem',
          lineHeight: 1.6,
          maxHeight: '400px',
          overflowY: 'auto',
          color: 'var(--text-color)',
        }}
      >
        {regulationsText}
      </div>

      {showAgreementCheckbox && (
        <label
          className="checkbox-label"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--sp-2)',
            cursor: 'pointer',
            fontWeight: 550,
            fontSize: '0.9rem',
            padding: 'var(--sp-2) 0',
          }}
        >
          <input
            type="checkbox"
            checked={agreed}
            onChange={handleCheckboxChange}
            id="regulations-agreement"
          />
          Tôi đã đọc và cam kết tuân thủ nghiêm ngặt mọi quy chế phòng thi.
        </label>
      )}
    </div>
  );
}
