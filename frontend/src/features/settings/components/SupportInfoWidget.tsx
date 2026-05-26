interface SupportInfoWidgetProps {
  email: string;
  hotline?: string;
}

export function SupportInfoWidget({ email, hotline }: SupportInfoWidgetProps) {
  return (
    <div
      className="support-info-widget"
      style={{
        padding: 'var(--sp-3)',
        borderRadius: 'var(--border-radius-md)',
        border: '1px solid var(--border-color)',
        backgroundColor: 'var(--bg-body)',
        fontSize: '0.85rem',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--sp-1)',
      }}
    >
      <span style={{ fontWeight: 600, color: 'var(--text-color)', marginBottom: 'var(--sp-1)' }}>
        Hỗ trợ kỹ thuật phòng thi
      </span>
      {email && (
        <span style={{ display: 'flex', gap: 'var(--sp-2)', alignItems: 'center' }}>
          <strong>Email:</strong>
          <a href={`mailto:${email}`} style={{ color: 'var(--primary-color)', textDecoration: 'none' }}>
            {email}
          </a>
        </span>
      )}
      {hotline && (
        <span style={{ display: 'flex', gap: 'var(--sp-2)', alignItems: 'center' }}>
          <strong>Hotline:</strong>
          <span style={{ color: 'var(--text-color)' }}>{hotline}</span>
        </span>
      )}
    </div>
  );
}
