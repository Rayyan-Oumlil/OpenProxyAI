import { Sparkline } from "../charts/Sparkline";
import { cn, formatPercent } from "../../lib/utils";

/** Which direction of change is good news: fewer errors and lower cost are good when they go down. */
export type GoodWhen = "up" | "down" | "neutral";

interface KpiCardProps {
  label: string;
  value: string;
  /** Relative change versus the previous period (0.25 = +25%); null when there is nothing to compare. */
  delta?: number | null;
  deltaLabel?: string;
  goodWhen?: GoodWhen;
  series?: number[];
  subtext?: string;
}

/** Changes smaller than this read as "no change" rather than a noisy +0.0%. */
const FLAT = 0.0005;

export function deltaTone(delta: number, goodWhen: GoodWhen): "good" | "bad" | "flat" {
  if (Math.abs(delta) < FLAT || goodWhen === "neutral") return "flat";
  return (delta > 0) === (goodWhen === "up") ? "good" : "bad";
}

function Delta({ delta, label, goodWhen }: { delta: number | null | undefined; label?: string; goodWhen: GoodWhen }) {
  if (delta == null) return label ? <span className="kpi__delta kpi__delta--none">No previous period to compare</span> : null;
  const tone = deltaTone(delta, goodWhen);
  const flat = Math.abs(delta) < FLAT;
  return (
    <span className={cn("kpi__delta", `kpi__delta--${tone}`)}>
      <span aria-hidden="true">{flat ? "→" : delta > 0 ? "↑" : "↓"}</span>
      {flat ? null : <span className="sr-only">{delta > 0 ? "Up" : "Down"} </span>}
      {flat ? "no change" : formatPercent(Math.abs(delta), 1)} {label}
    </span>
  );
}

export function KpiCard({ label, value, delta, deltaLabel, goodWhen = "neutral", series, subtext }: KpiCardProps) {
  return (
    <article className="kpi">
      <span className="kpi__label">{label}</span>
      <strong className="kpi__value">{value}</strong>
      <Delta delta={delta} label={deltaLabel} goodWhen={goodWhen} />
      {subtext ? <span className="kpi__sub">{subtext}</span> : null}
      {series && series.length > 1 ? <Sparkline values={series} className="sparkline kpi__spark" /> : null}
    </article>
  );
}
