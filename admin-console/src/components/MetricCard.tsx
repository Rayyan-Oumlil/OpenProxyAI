type MetricCardProps = {
  label: string;
  value: string;
  accent: "amber" | "teal" | "rose" | "sky";
};

export function MetricCard({ label, value, accent }: MetricCardProps) {
  return (
    <article className={`metric-card metric-${accent}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

