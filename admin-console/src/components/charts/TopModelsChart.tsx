import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { CostByModel } from "../../api/types";
import { formatCost } from "../../lib/utils";

interface TopModelsChartProps {
  data: CostByModel[];
}

const COLORS = [
  "var(--accent-sky)",
  "var(--accent-teal)",
  "var(--accent-amber)",
  "var(--accent-rose)",
  "#7c6bbf",
];

interface TooltipProps {
  active?: boolean;
  payload?: { value: number; payload: CostByModel }[];
}

function CustomTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--line)",
        borderRadius: 10,
        padding: "8px 12px",
        fontSize: 13,
        fontFamily: "Inter, sans-serif",
      }}
    >
      <p style={{ fontWeight: 600, color: "var(--text)" }}>{d.model}</p>
      <p style={{ color: "var(--muted)", margin: "2px 0" }}>{d.provider}</p>
      <p style={{ color: "var(--accent-sky-dark)", fontWeight: 500 }}>{formatCost(d.cost_usd)}</p>
      <p style={{ color: "var(--muted)" }}>{d.requests.toLocaleString()} requests</p>
    </div>
  );
}

export function TopModelsChart({ data }: TopModelsChartProps) {
  if (!data.length) {
    return (
      <div
        style={{
          height: 140,
          display: "grid",
          placeItems: "center",
          color: "var(--muted)",
          fontSize: 14,
        }}
      >
        No model usage data yet
      </div>
    );
  }

  const top5 = [...data].sort((a, b) => b.cost_usd - a.cost_usd).slice(0, 5);

  return (
    <ResponsiveContainer width="100%" height={top5.length * 44 + 20}>
      <BarChart
        data={top5}
        layout="vertical"
        margin={{ top: 0, right: 60, bottom: 0, left: 8 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" horizontal={false} />
        <XAxis
          type="number"
          tick={{ fontSize: 11, fill: "var(--muted)", fontFamily: "Inter" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `$${v.toFixed(3)}`}
        />
        <YAxis
          type="category"
          dataKey="model"
          width={140}
          tick={{ fontSize: 11, fill: "var(--text)", fontFamily: "Inter" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v: string) => (v.length > 22 ? v.slice(0, 22) + "…" : v)}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(14,165,233,0.06)" }} />
        <Bar dataKey="cost_usd" radius={[0, 6, 6, 0]}>
          {top5.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
