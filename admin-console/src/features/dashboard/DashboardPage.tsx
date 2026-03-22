import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  CheckCircle,
  XCircle,
  DollarSign,
  ShieldX,
  ShieldAlert,
  Zap,
  TrendingUp,
  Download,
} from "lucide-react";

import { toast } from "sonner";

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
    <div className={cn("metric-card", `metric-card--${accent}`)}>
      <div className="flex items-center justify-between">
        <span className="text-muted-sm">{label}</span>
        <Icon size={16} className={cn("metric-icon", `metric-icon--${accent}`)} aria-hidden />
      </div>
      <strong>{value}</strong>
      {subtext && <span className="text-muted-xs">{subtext}</span>}
    </div>
  );
}

function PolicyStrip({ data }: { data: PolicyAnalyticsResponse }) {
  const getCount = (action: string) =>
    data.by_action.find((a) => a.action === action)?.count ?? 0;
  return (
    <div className="flex flex-wrap gap-2 text-sm policy-strip">
      <span className="chip-allow">
        Allow: {getCount("allow").toLocaleString()}
      </span>
      <span className="chip-log">
        Log Only: {getCount("log_only").toLocaleString()}
      </span>
      <span className="chip-block">
        Block: {getCount("block").toLocaleString()}
      </span>
    </div>
  );
}

export function DashboardPage() {
  const { token, user } = useAuth();
  const [period, setPeriod] = useState(30);
  const [teamFilter, setTeamFilter] = useState("");
  const [isExportingCompliance, setIsExportingCompliance] = useState(false);

  const teamsQuery = useQuery({
    queryKey: ["teams", token],
    queryFn: () => apiClient.get<import("../../api/types").TeamResponse[]>("/api/v1/teams", token!),
    enabled: Boolean(token) && user?.role === "admin",
  });

  const downloadComplianceReport = async () => {
    if (!token || isExportingCompliance) return;
    try {
      setIsExportingCompliance(true);
      const blob = await apiClient.getBlob(
        `/api/v1/analytics/compliance/export?period_days=${period}`,
        token
      );
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "compliance-report.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to export compliance report");
    } finally {
      setIsExportingCompliance(false);
    }
  };

  const overviewQuery = useQuery({
    queryKey: ["analytics", "overview", period, teamFilter, token],
    queryFn: () => {
      const params = new URLSearchParams({ period_days: String(period) });
      if (teamFilter) params.set("team_id", teamFilter);
      return apiClient.get<AnalyticsResponse>(`/api/v1/analytics/overview?${params.toString()}`, token!);
    },
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

  const { overview, by_model, by_team, daily_trend } = overviewQuery.data;

  return (
    <section className="page-wrap">
      <header className="flex items-end justify-between flex-wrap gap-2">
        <div className="page-header">
          <p className="eyebrow">Last {period} days</p>
          <h1>Gateway Dashboard</h1>
        </div>
        <div className="flex gap-1.5">
          <button
            type="button"
            onClick={downloadComplianceReport}
            disabled={isExportingCompliance || !token}
            className="btn-outline px-3 py-1.5 rounded-lg text-sm transition-colors flex items-center gap-1.5"
            aria-label={isExportingCompliance ? "Exporting compliance report" : "Export compliance report as CSV"}
          >
            <Download size={14} aria-hidden />
            {isExportingCompliance ? "Exporting..." : "Export Compliance CSV"}
          </button>
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setPeriod(opt.value)}
              className={cn(
                "btn-period",
                period === opt.value ? "btn-period-active" : "btn-period-inactive"
              )}
              aria-label={`Show last ${opt.label}`}
            >
              {opt.label}
            </button>
          ))}
          {user?.role === "admin" && teamsQuery.data && teamsQuery.data.length > 0 && (
            <select
              value={teamFilter}
              onChange={(e) => setTeamFilter(e.target.value)}
              className="select-filter"
              aria-label="Filter by team"
            >
              <option value="">All teams</option>
              {teamsQuery.data.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          )}
        </div>
      </header>

      {policyQuery.data && (
        <div className="surface-panel panel-pad-sm">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm font-medium text-muted-sm">
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
        <MetricCard
          label="Projected Month-End Cost"
          value={
            overview.projected_month_end_cost_usd != null
              ? formatCost(overview.projected_month_end_cost_usd)
              : "—"
          }
          icon={TrendingUp}
          accent="violet"
          subtext={
            overview.forecast_basis_days != null
              ? `Based on ${overview.forecast_basis_days} elapsed day(s)`
              : undefined
          }
        />
        <MetricCard label="Policy Blocked" value={formatNumber(overview.policy_blocked_requests)} icon={ShieldX} accent="rose" />
        <MetricCard label="Policy Flagged" value={formatNumber(overview.policy_flagged_requests)} icon={ShieldAlert} accent="amber" />
        <MetricCard
          label="Cache Hit Rate"
          value={overview.cache_hit_rate != null
            ? `${Math.round((overview.cache_hit_rate ?? 0) * 100)}%`
            : "—"}
          icon={Zap}
          accent="violet"
          subtext={overview.cache_hit_rate == null ? "Enable caching to track hits" : undefined}
        />
      </section>

      <section className="surface-panel">
        <div className="flex items-center justify-between mb-3">
          <h2 className="section-title">Daily Trend</h2>
          <span className="text-muted-xs">Requests + Cost</span>
        </div>
        <DailyTrendChart data={daily_trend ?? []} />
      </section>

      {user?.role === "admin" && by_team && by_team.length > 0 && (
        <section className="surface-panel">
          <h2 className="section-title-mb">Cost by Team</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>Team</th>
                <th className="text-right">Requests</th>
                <th className="text-right">Cost</th>
              </tr>
            </thead>
            <tbody>
              {by_team.map((t) => (
                <tr key={t.team_id}>
                  <td className="font-medium">{t.name}</td>
                  <td className="text-right text-muted">{formatNumber(t.requests)}</td>
                  <td className="text-right font-medium">{formatCost(t.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <div className="grid-two-col gap-4">
        <section className="surface-panel">
          <h2 className="section-title-mb">Top Models by Cost</h2>
          <TopModelsChart data={by_model ?? []} />
        </section>

        <section className="surface-panel">
          <h2 className="section-title-mb">Performance</h2>
          <table className="data-table">
            <tbody>
              <tr>
                <td className="text-muted">Avg Latency</td>
                <td className="font-medium">{formatLatency(overview.avg_latency_ms)}</td>
              </tr>
              <tr>
                <td className="text-muted">p50 Latency</td>
                <td className="font-medium">
                  {overview.p50_latency_ms != null ? formatLatency(overview.p50_latency_ms) : "—"}
                </td>
              </tr>
              <tr>
                <td className="text-muted">p95 Latency</td>
                <td className="font-medium">
                  {overview.p95_latency_ms != null ? formatLatency(overview.p95_latency_ms) : "—"}
                </td>
              </tr>
              <tr>
                <td className="text-muted">p99 Latency</td>
                <td className="font-medium">
                  {overview.p99_latency_ms != null ? formatLatency(overview.p99_latency_ms) : "—"}
                </td>
              </tr>
              <tr>
                <td className="text-muted">Avg TTFT</td>
                <td className="font-medium">{formatLatency(overview.avg_ttft_ms)}</td>
              </tr>
              <tr>
                <td className="text-muted">Total Tokens</td>
                <td className="font-medium">{formatNumber(overview.total_tokens)}</td>
              </tr>
              <tr>
                <td className="text-muted">Cost / Request</td>
                <td className="font-medium">
                  {overview.total_requests > 0
                    ? formatCost(overview.total_cost_usd / overview.total_requests)
                    : "—"}
                </td>
              </tr>
              <tr>
                <td className="text-muted">Success Rate</td>
                <td className="font-medium">
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
