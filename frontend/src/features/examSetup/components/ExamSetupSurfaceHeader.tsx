type ExamSetupSurfaceHeaderProps = {
  eyebrow: string;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
};

export function ExamSetupSurfaceHeader({
  eyebrow,
  title,
  description,
  actionLabel,
  onAction,
}: ExamSetupSurfaceHeaderProps) {
  return (
    <section className="dashboard-hero setup-hero">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {actionLabel && onAction ? (
        <button type="button" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </section>
  );
}