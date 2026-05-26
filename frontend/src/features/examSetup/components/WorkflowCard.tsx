import { Link } from 'react-router-dom';

type WorkflowCardProps = {
  title: string;
  description: string;
  to: string;
  items: string[];
};

export function WorkflowCard({ title, description, to, items }: WorkflowCardProps) {
  return (
    <article className="card" style={{ display: 'grid', gap: 'var(--sp-4)' }}>
      <div style={{ display: 'grid', gap: 'var(--sp-2)' }}>
        <h3>{title}</h3>
        <p className="muted">{description}</p>
      </div>
      <ul className="setup-inline-notes" aria-label={`${title} scope`}>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <div>
        <Link className="primary-button" to={to}>
          Mở workflow
        </Link>
      </div>
    </article>
  );
}