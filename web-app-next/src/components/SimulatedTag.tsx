export default function SimulatedTag() {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded border border-line bg-surface px-2 py-0.5 font-mono text-[11px] uppercase tracking-widest text-ink-dim"
      title="Simulated traffic generated in your browser. It mirrors the real pipeline in backend/app/routes/proxy.py."
    >
      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-signal" />
      Simulated
    </span>
  );
}
