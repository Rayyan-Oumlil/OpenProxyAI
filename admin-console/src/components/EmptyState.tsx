type EmptyStateProps = {
  title: string;
  detail: string;
};

export function EmptyState({ title, detail }: EmptyStateProps) {
  return (
    <section className="surface-panel empty-state" aria-live="polite">
      <h3>{title}</h3>
      <p>{detail}</p>
    </section>
  );
}

