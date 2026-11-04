import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type { AnalyticsResponse, CostByKey, CostByTeam, CostByUser, OrganizationResponse, TeamResponse } from "../../api/types";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { LoadingState } from "../../components/LoadingState";
import { BudgetBurndown } from "../../components/charts/BudgetBurndown";
import { DailyTrendChart } from "../../components/charts/DailyTrendChart";
import { TopModelsChart } from "../../components/charts/TopModelsChart";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { KpiCard } from "../../components/ui/KpiCard";
import { PageHeader } from "../../components/ui/PageHeader";
import { useAuth } from "../../state/AuthContext";
import { cn, formatCost, formatLatency, formatNumber, formatPercent } from "../../lib/utils";
import { burndown, canCompare, change, splitPeriods, totals } from "./metrics";

const PERIOD_OPTIONS = [
  { label: "7 days", value: 7 },
  { label: "30 days", value: 30 },
  { label: "90 days", value: 90 },
];

function trendQuery(periodDays: number, teamId: string): string {
  const params = new URLSearchParams({ period_days: String(periodDays) });
  if (teamId) params.set("team_id", teamId);
  return `/api/v1/analytics/overview?${params.toString()}`;
}

const TEAM_COLUMNS: Column<CostByTeam>[] = [
  { key: "team", header: "Team", cell: (t) => t.name },
  { key: "requests", header: "Requests", align: "right", mono: true, cell: (t) => formatNumber(t.requests) },
  { key: "cost", header: "Cost", align: "right", mono: true, cell: (t) => formatCost(t.cost_usd) },
];

const KEY_COLUMNS: Column<CostByKey>[] = [
  { key: "key", header: "API key", cell: (k) => k.name ?? "Unnamed" },
  { key: "prefix", header: "Prefix", mono: true, cell: (k) => k.key_prefix },
  { key: "requests", header: "Requests", align: "right", mono: true, cell: (k) => formatNumber(k.requests) },
  { key: "tokens", header: "Tokens", align: "right", mono: true, cell: (k) => formatNumber(k.tokens) },
  { key: "cost", header: "Cost", align: "right", mono: true, cell: (k) => formatCost(k.cost_usd) },
];

const USER_COLUMNS: Column<CostByUser>[] = [
  { key: "user", header: "User", cell: (u) => u.email },
  { key: "requests", header: "Requests", align: "right", mono: true, cell: (u) => formatNumber(u.requests) },
  { key: "tokens", header: "Tokens", align: "right", mono: true, cell: (u) => formatNumber(u.tokens) },
  { key: "cost", header: "Cost", align: "right", mono: true, cell: (u) => formatCost(u.cost_usd) },
];

export function DashboardPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [period, setPeriod] = useState(30);
  const [teamFilter, setTeamFilter] = useState("");
  const [isExportingCompliance, setIsExportingCompliance] = useState(false);

  const teamsQuery = useQuery({
    queryKey: ["teams", token],
    queryFn: () => apiClient.get<TeamResponse[]>("/api/v1/teams", token!),
    enabled: Boolean(token) && isAdmin,
  });

  const overviewQuery = useQuery({
    queryKey: ["analytics", "overview", period, teamFilter, token],
    queryFn: () => apiClient.get<AnalyticsResponse>(trendQuery(period, teamFilter), token!),
    enabled: Boolean(token),
  });

  const comparable = canCompare(period);
  // Twice the window, used only for its daily trend: the second half is the previous period.
  const previousQuery = useQuery({
    queryKey: ["analytics", "overview-2x", period, teamFilter, token],
    queryFn: () => apiClient.get<AnalyticsResponse>(trendQuery(period * 2, teamFilter), token!),
    enabled: Boolean(token) && comparable,
  });

  const endIso = overviewQuery.data?.generated_at.slice(0, 10) ?? "";
  const dayOfMonth = endIso ? Number(endIso.slice(8, 10)) : 0;
  const monthQuery = useQuery({
    queryKey: ["analytics", "month", dayOfMonth, token],
    queryFn: () => apiClient.get<AnalyticsResponse>(trendQuery(dayOfMonth, ""), token!),
    enabled: Boolean(token) && dayOfMonth > 0 && !teamFilter,
  });

  const orgQuery = useQuery({
    queryKey: ["organization", "current", token],
    queryFn: () => apiClient.get<OrganizationResponse>("/api/v1/organizations/current", token!),
    enabled: Boolean(token) && isAdmin,
  });

  async function downloadComplianceReport() {
    if (!token || isExportingCompliance) return;
    try {
      setIsExportingCompliance(true);
      const blob = await apiClient.getBlob(`/api/v1/analytics/compliance/export?period_days=${period}`, token);
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
  }

  if (overviewQuery.isLoading) return <LoadingState label="Loading overview metrics..." />;
  if (overviewQuery.isError)
    return (
      <ErrorState
        title="Unable to load overview"
        detail={overviewQuery.error instanceof Error ? overviewQuery.error.message : "Unknown error"}
      />
    );
  if (!overviewQuery.data) return <EmptyState title="No metrics yet" detail="Send traffic through your gateway first." />;

  const { overview, by_model, by_team, by_user, by_key, daily_trend } = overviewQuery.data;

  const hasPrevious = comparable && previousQuery.data !== undefined;
  const { current, previous } = splitPeriods(
    hasPrevious ? previousQuery.data!.daily_trend : daily_trend,
    endIso,
    period,
    hasPrevious,
  );
  const now = totals(current);
  const before = previous ? totals(previous) : null;
  const vs = `vs previous ${period} days`;

  const budget = orgQuery.data?.budget_monthly_usd != null ? Number(orgQuery.data.budget_monthly_usd) : null;
  const month = monthQuery.data ? burndown(monthQuery.data.daily_trend, endIso, budget) : null;

  const successRate = overview.total_requests > 0 ? overview.successful_requests / overview.total_requests : null;

  return (
    <section className="page-wrap">
      <PageHeader
        title="Gateway dashboard"
        description={`Last ${period} days${teamFilter ? " for the selected team" : ""}.`}
        actions={
          <div className="dash-controls">
            <div className="dash-periods" role="group" aria-label="Time period">
              {PERIOD_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setPeriod(opt.value)}
                  aria-pressed={period === opt.value}
                  className={cn("btn-period", period === opt.value ? "btn-period-active" : "btn-period-inactive")}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            {isAdmin && teamsQuery.data && teamsQuery.data.length > 0 ? (
              <select value={teamFilter} onChange={(e) => setTeamFilter(e.target.value)} className="select-filter" aria-label="Filter by team">
                <option value="">All teams</option>
                {teamsQuery.data.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            ) : null}
            <button type="button" onClick={downloadComplianceReport} disabled={isExportingCompliance || !token} className="btn-outline">
              <Download size={14} aria-hidden /> {isExportingCompliance ? "Exporting..." : "Compliance CSV"}
            </button>
          </div>
        }
      />

      <section className="kpi-grid" aria-label="Key metrics">
        <KpiCard label="Requests" value={formatNumber(overview.total_requests)} delta={before ? change(now.requests, before.requests) : null} deltaLabel={vs} series={current.map((d) => d.requests)} />
        <KpiCard label="Cost" value={formatCost(overview.total_cost_usd)} delta={before ? change(now.cost, before.cost) : null} deltaLabel={vs} goodWhen="down" series={current.map((d) => d.cost_usd)} />
        <KpiCard label="Tokens" value={formatNumber(overview.total_tokens)} delta={before ? change(now.tokens, before.tokens) : null} deltaLabel={vs} series={current.map((d) => d.tokens)} />
        <KpiCard
          label="Avg latency"
          value={formatLatency(overview.avg_latency_ms)}
          delta={before ? change(now.avgLatencyMs, before.avgLatencyMs) : null}
          deltaLabel={vs}
          goodWhen="down"
          series={current.map((d) => d.avg_latency_ms)}
          subtext={overview.p95_latency_ms != null ? `p95 ${formatLatency(overview.p95_latency_ms)}` : undefined}
        />
      </section>

      <section className="kpi-grid kpi-grid--governance" aria-label="Reliability and governance">
        <KpiCard label="Success rate" value={successRate != null ? formatPercent(successRate, 1) : "—"} subtext={`${formatNumber(overview.failed_requests)} failed`} />
        <KpiCard label="Policy blocked" value={formatNumber(overview.policy_blocked_requests)} subtext="Stopped before the provider" />
        <KpiCard label="Policy flagged" value={formatNumber(overview.policy_flagged_requests)} subtext="Allowed and logged" />
        <KpiCard
          label="Cache hit rate"
          value={overview.cache_hit_rate != null ? formatPercent(overview.cache_hit_rate, 0) : "—"}
          subtext={overview.cache_hit_rate == null ? "Enable caching to track hits" : undefined}
        />
      </section>

      <section className="surface-panel">
        <h2 className="section-title-mb">Budget burn-down this month</h2>
        {teamFilter ? (
          <p className="trace-note">The monthly budget applies to the whole organization. Choose All teams to see it.</p>
        ) : month ? (
          <>
            <BudgetBurndown burndown={month} />
            {month.budget == null ? (
              <p className="trace-note">No monthly budget is set. Add one in Organization settings to track spend against it.</p>
            ) : null}
          </>
        ) : monthQuery.isError ? (
          <p className="trace-note" role="alert">Unable to load this month's spend.</p>
        ) : (
          <p className="trace-note">Loading this month's spend...</p>
        )}
      </section>

      <section className="surface-panel">
        <div className="flex items-center justify-between mb-3">
          <h2 className="section-title">Daily trend</h2>
          <span className="text-muted-xs">Requests and cost</span>
        </div>
        <DailyTrendChart data={daily_trend ?? []} />
      </section>

      <div className="grid-two-col gap-4">
        <section className="surface-panel">
          <h2 className="section-title-mb">Top models by cost</h2>
          <TopModelsChart data={by_model ?? []} />
        </section>
        {isAdmin && by_team && by_team.length > 0 ? (
          <section className="surface-panel">
            <h2 className="section-title-mb">Cost by team</h2>
            <DataTable caption="Cost by team" columns={TEAM_COLUMNS} rows={by_team} getRowId={(t) => t.team_id} empty={{ title: "No team spend", detail: "" }} density="compact" />
          </section>
        ) : null}
      </div>

      {isAdmin && by_key && by_key.length > 0 ? (
        <section className="surface-panel">
          <h2 className="section-title-mb">Cost by API key</h2>
          <DataTable caption="Cost by API key" columns={KEY_COLUMNS} rows={by_key} getRowId={(k) => k.api_key_id} empty={{ title: "No key spend", detail: "" }} density="compact" />
        </section>
      ) : null}

      {isAdmin && by_user && by_user.length > 0 ? (
        <section className="surface-panel">
          <h2 className="section-title-mb">Cost by user</h2>
          <DataTable caption="Cost by user" columns={USER_COLUMNS} rows={by_user} getRowId={(u) => u.user_id} empty={{ title: "No user spend", detail: "" }} density="compact" />
        </section>
      ) : null}
    </section>
  );
}
