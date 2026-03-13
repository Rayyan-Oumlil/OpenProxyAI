type ErrorStateProps = {
  title: string;
  detail: string;
};

export function ErrorState({ title, detail }: ErrorStateProps) {
  return (
    <section className="surface-panel error-state" role="alert">
      <h3>{title}</h3>
      <p>{detail}</p>
    </section>
  );
}

