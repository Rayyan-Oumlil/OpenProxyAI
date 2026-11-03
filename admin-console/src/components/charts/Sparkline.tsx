interface SparklineProps {
  values: number[];
  /** Decorative by default; the number beside it carries the meaning. */
  className?: string;
}

const WIDTH = 100;
const HEIGHT = 28;
const PAD = 2;

/** A tiny trend line with no axes. A flat or single-point series draws a level line, never NaN. */
export function sparklinePoints(values: number[]): string {
  if (values.length === 0) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min;
  const step = values.length > 1 ? (WIDTH - PAD * 2) / (values.length - 1) : 0;
  return values
    .map((value, i) => {
      const x = values.length > 1 ? PAD + i * step : WIDTH / 2;
      const y = span === 0 ? HEIGHT / 2 : HEIGHT - PAD - ((value - min) / span) * (HEIGHT - PAD * 2);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

export function Sparkline({ values, className }: SparklineProps) {
  return (
    <svg className={className ?? "sparkline"} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none" aria-hidden="true" focusable="false">
      <polyline points={sparklinePoints(values)} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
