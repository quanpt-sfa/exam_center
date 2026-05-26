interface ExamRegulationsEditorProps {
  value: string;
  onChange: (value: string) => void;
}

export function ExamRegulationsEditor({ value, onChange }: ExamRegulationsEditorProps) {
  return (
    <div className="settings-regulation-grid">
      <div className="settings-regulation-pane">
        <span className="settings-regulation-pane-title">Nội dung văn bản</span>
        <textarea
          id="exam_regulations"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={8}
          placeholder="Nhập nội quy phòng thi..."
          className="settings-regulation-textarea"
        />
      </div>
      <div className="settings-regulation-pane">
        <span className="settings-regulation-pane-title">Xem trước trực quan (XSS-safe)</span>
        <div className="regulations-preview-panel">
          {value || <span className="muted">Chưa nhập nội quy phòng thi.</span>}
        </div>
      </div>
    </div>
  );
}
