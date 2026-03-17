import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, CheckCircle, XCircle, DollarSign, ShieldX, ShieldAlert, Zap } from "lucide-react";

import { apiClient } from "../../api/client";
import type { AnalyticsResponse, PolicyAnalyticsResponse } from "../../api/types";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { LoadingState } from "../../components/LoadingState";
import { DailyTrendChart } from "../../components/charts/DailyTrendChart";
import { TopModelsChart } from "../../components/charts/TopModelsChart";
import { useAuth } from "../../state/AuthContext";
import { formatCost, formatNumber, formatLatency, cn } from "../../lib/utils";

const PERIOD_OPTIONS = [
  { label: "7 days", value: 7 },
  { label: "30 days", value: 30 },
  { label: "90 days", value: 90 },
];

const ACCENT_COLORS: Record<string, string> = {
  amber: "var(--accent-amber)",
  teal: "var(--accent-teal)",
  rose: "var(--accent-rose)",
  sky: "var(--accent-sky)",
  violet: "#7c3aed",
};

function MetricCard({
  label,
  value,
  icon: Icon,
  accent,
  subtext,
}: {
  label: string;
  value: string;
  icon: React.ElementType;
  accent: "amber" | "teal" | "rose" | "sky" | "violet";
  subtext?: string;
}) {
  return (
    <div className="metric-card" style={{ boxShadow: `inset 0 3px 0 ${ACCENT_COLORS[accent]}` }}>
      <div className="flex items-center justify-between">
        <span style={{ color: "var(--muted)", fontSize: "0.88rem" }}>{label}</span>
        <Icon size={16} style={{ color: ACCENT_COLORS[accent] }} />
      </div>
      <strong style={{ fontSize: "1.25rem" }}>{value}</strong>
      {subtext && <span style={{ color: "var(--muted)", fontSize: "0.75rem" }}>{subtext}</span>}
    </div>
  );
}

function PolicyStrip({ data }: { data: PolicyAnalyticsResponse }) {
  const getCount = (action: string) =>
    data.by_action.find((a) => a.action === action)?.count ?? 0;
  return (
    <div className="flex flex-wrap gap-2 text-sm">
      <span
        className="flex items-center gap-1.5 rounded-full px-3 py-1"
        style={{ background: "rgba(15,138,123,0.12)", color: "#0d5f55" }}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-current" />
        Allow: {getCount("allow").toLocaleString()}
      </span>
      <span
        className="flex items-center gap-1.5 rounded-full px-3 py-1"
        style={{ background: "rgba(217,122,15,0.12)", color: "#7a4500" }}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-current" />
        Log Only: {getCount("log_only").toLocaleString()}
      </span>
      <span
        className="flex items-center gap-1.5 rounded-full px-3 py-1"
        style={{ background: "rgba(204,79,79,0.12)", color: "#8a3131" }}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-current" />
        Block: {getCount("block").toLocaleString()}
      </span>
    </div>
  );
}

export function DashboardPage() {
  const { token } = useAuth();
  const [period, setPeriod] = useState(30);

  const overviewQuery = useQuery({
    queryKey: ["analytics", "overview", period, token],
    queryFn: () =>
      apiClient.get<AnalyticsResponse>(`/api/v1/analytics/overview?period_days=${period}`, token!),
    enabled: Boolean(token),
  });

  const policyQuery = useQuery({
    queryKey: ["analytics", "policy", period, token],
    queryFn: () =>
      apiClient.get<PolicyAnalyticsResponse>(
        `/api/v1/analytics/policy?period_days=${period}`,
        token!
      ),
    enabled: Boolean(token),
  });

  if (overviewQuery.isLoading) return <LoadingState label="Loading overview metrics..." />;
  if (overviewQuery.isError)
    return (
      <ErrorState
        title="Unable to load overview"
        detail={
          overviewQuery.error instanceof Error ? overviewQuery.error.message : "Unknown error"
        }
      />
    );
  if (!overviewQuery.data)
    return <EmptyState title="No metrics yet" detail="Send traffic through your gateway first." />;

  const { overview, by_model, daily_trend } = overviewQuery.data;

  return (
    <section className="page-wrap">
      <header className="flex items-end justify-between flex-wrap gap-2">
        <div className="page-header">
          <p className="eyebrow">Last {period} days</p>
          <h1>Gateway Dashboard</h1>
        </div>
        <div className="flex gap-1.5">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setPeriod(opt.value)}
              className={cn("px-3 py-1.5 rounded-lg text-sm transition-colors")}
              style={{
                background: period === opt.value ? "var(--accent-sky)" : "transparent",
                color: period === opt.value ? "#fff" : "var(--muted)",
                border: `1px solid ${period === opt.value ? "var(--accent-sky)" : "var(--line)"}`,
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </header>

      {policyQuery.data && (
        <div className="surface-panel" style={{ padding: "0.75rem 1rem" }}>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm font-medium" style={{ color: "var(--muted)" }}>
              Policy decisions:
            </span>
            <PolicyStrip data={policyQuery.data} />
          </div>
        </div>
      )}

      <section className="metrics-grid">
        <MetricCard label="Total Requests" value={formatNumber(overview.total_requests)} icon={Activity} accent="amber" />
        <MetricCard label="Successful" value={formatNumber(overview.successful_requests)} icon={CheckCircle} accent="teal" />
        <MetricCard label="Failed" value={formatNumber(overview.failed_requests)} icon={XCircle} accent="rose" />
        <MetricCard label="Total Cost" value={formatCost(overview.total_cost_usd)} icon={DollarSign} accent="sky" />
        <MetricCard label="Policy Blocked" value={formatNumber(overview.policy_blocked_requests)} icon={ShieldX} accent="rose" />
        <MetricCard label="Policy Flagged" value={formatNumber(overview.policy_flagged_requests)} icon={ShieldAlert} accent="amber" />
        <MetricCard
          label="Cache Hit Rate"
          value={(overview as { cache_hit_rate?: number }).cache_hit_rate != null
            ? `${Math.round(((overview as { cache_hit_rate?: number }).cache_hit_rate ?? 0) * 100)}%`
            : "—"}
          icon={Zap}
          accent="violet"
          subtext={(overview as { cache_hit_rate?: number }).cache_hit_rate == null ? "Enable caching to track hits" : undefined}
        />
      </section>

      <section className="surface-panel">
        <div className="flex items-center justify-between mb-3">
          <h2 style={{ fontSize: "1rem", fontWeight: 600 }}>Daily Trend</h2>
          <span className="text-xs" style={{ color: "var(--muted)" }}>Requests + Cost</span>
        </div>
        <DailyTrendChart data={daily_trend ?? []} />
      </section>

      <div className="grid gap-4" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <section className="surface-panel">
          <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "0.75rem" }}>Top Models by Cost</h2>
          <TopModelsChart data={by_model ?? []} />
        </section>

        <section className="surface-panel">
          <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "0.75rem" }}>Performance</h2>
          <table className="data-table">
            <tbody>
              <tr>
                <td style={{ color: "var(--muted)" }}>Avg Latency</td>
                <td style={{ fontWeight: 500 }}>{formatLatency(overview.avg_latency_ms)}</td>
              </tr>
              <tr>
                <td style={{ color: "var(--muted)" }}>p50 Latency</td>
                <td style={{ fontWeight: 500 }}>
                  {overview.p50_latency_ms != null ? formatLatency(overview.p50_latency_ms) : "—"}
                </td>
              </tr>
              <tr>
                <td style={{ color: "var(--muted)" }}>p95 Latency</td>
                <td style={{ fontWeight: 500 }}>
                  {overview.p95_latency_ms != null ? formatLatency(overview.p95_latency_ms) : "—"}
                </td>
              </tr>
              <tr>
                <td style={{ color: "var(--muted)" }}>p99 Latency</td>
                <td style={{ fontWeight: 500 }}>
                  {overview.p99_latency_ms != null ? formatLatency(overview.p99_latency_ms) : "—"}
                </td>
              </tr>
              <tr>
                <td style={{ color: "var(--muted)" }}>Avg TTFT</td>
                <td style={{ fontWeight: 500 }}>{formatLatency(overview.avg_ttft_ms)}</td>
              </tr>
              <tr>
                <td style={{ color: "var(--muted)" }}>Total Tokens</td>
                <td style={{ fontWeight: 500 }}>{formatNumber(overview.total_tokens)}</td>
              </tr>
              <tr>
                <td style={{ color: "var(--muted)" }}>Cost / Request</td>
                <td style={{ fontWeight: 500 }}>
                  {overview.total_requests > 0
                    ? formatCost(overview.total_cost_usd / overview.total_requests)
                    : "—"}
                </td>
              </tr>
              <tr>
                <td style={{ color: "var(--muted)" }}>Success Rate</td>
                <td style={{ fontWeight: 500 }}>
                  {overview.total_requests > 0
                    ? `${((overview.successful_requests / overview.total_requests) * 100).toFixed(1)}%`
                    : "—"}
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    </section>
  );
}
