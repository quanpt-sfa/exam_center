type CompactStatItem = {
  label: string;
  value: number | string;
  hint?: string;
};

export function CompactStatBar({ items }: { items: CompactStatItem[] }) {
  return (
    <div className="compact-statbar">
      {items.map((item) => (
        <article key={item.label} className="compact-statbar__item">
          <span>{item.label}</span>
          <strong>{item.value}</strong>
          {item.hint ? <small>{item.hint}</small> : null}
        </article>
      ))}
    </div>
  );
}
