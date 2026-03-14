import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { DailyUsageTrend } from "../../api/types";
import { formatDateShort, formatCost, formatNumber } from "../../lib/utils";

interface DailyTrendChartProps {
  data: DailyUsageTrend[];
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
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
      <p style={{ fontWeight: 600, marginBottom: 4, color: "var(--text)" }}>
        {label}
      </p>
      {payload.map((entry) => (
        <p key={entry.name} style={{ color: entry.color, margin: "2px 0" }}>
          {entry.name === "requests"
            ? `Requests: ${formatNumber(entry.value)}`
            : `Cost: ${formatCost(entry.value)}`}
        </p>
      ))}
    </div>
  );
}

export function DailyTrendChart({ data }: DailyTrendChartProps) {
  if (!data.length) {
    return (
      <div
        style={{
          height: 160,
          display: "grid",
          placeItems: "center",
          color: "var(--muted)",
          fontSize: 14,
        }}
      >
        No trend data yet
      </div>
    );
  }

  const formatted = data.map((d) => ({
    ...d,
    date: formatDateShort(d.date),
  }));

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={formatted} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="var(--accent-teal)" stopOpacity={0.25} />
            <stop offset="95%" stopColor="var(--accent-teal)" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="colorCost" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="var(--accent-sky)" stopOpacity={0.25} />
            <stop offset="95%" stopColor="var(--accent-sky)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "var(--muted)", fontFamily: "Inter" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          yAxisId="left"
          tick={{ fontSize: 11, fill: "var(--muted)", fontFamily: "Inter" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={formatNumber}
          width={40}
        />
        <YAxis
          yAxisId="right"
          orientation="right"
          tick={{ fontSize: 11, fill: "var(--muted)", fontFamily: "Inter" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `$${v.toFixed(2)}`}
          width={50}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: 12, fontFamily: "Inter", paddingTop: 8 }}
        />
        <Area
          yAxisId="left"
          type="monotone"
          dataKey="requests"
          stroke="var(--accent-teal)"
          strokeWidth={2}
          fill="url(#colorRequests)"
          name="requests"
        />
        <Area
          yAxisId="right"
          type="monotone"
          dataKey="cost_usd"
          stroke="var(--accent-sky)"
          strokeWidth={2}
          fill="url(#colorCost)"
          name="cost_usd"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
