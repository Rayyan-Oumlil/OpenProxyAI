type LoadingStateProps = {
  label: string;
};

export function LoadingState({ label }: LoadingStateProps) {
  return (
    <section className="surface-panel loading-state" aria-live="polite" aria-busy="true">
      <div className="loader" />
      <p>{label}</p>
    </section>
  );
}

