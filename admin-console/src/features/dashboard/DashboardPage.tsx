import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../../api/client";
import type { AnalyticsResponse } from "../../api/types";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { LoadingState } from "../../components/LoadingState";
import { MetricCard } from "../../components/MetricCard";
import { useAuth } from "../../state/AuthContext";

function formatUsd(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 4,
  }).format(value);
}

export function DashboardPage() {
  const { token } = useAuth();

  const overviewQuery = useQuery({
    queryKey: ["analytics", "overview", token],
    queryFn: () => apiClient.get<AnalyticsResponse>("/api/v1/analytics/overview?period_days=30", token!),
    enabled: Boolean(token),
  });

  if (overviewQuery.isLoading) {
    return <LoadingState label="Loading overview metrics..." />;
  }

  if (overviewQuery.isError) {
    return (
      <ErrorState
        title="Unable to load overview"
        detail={overviewQuery.error instanceof Error ? overviewQuery.error.message : "Unknown error"}
      />
    );
  }

  if (!overviewQuery.data) {
    return <EmptyState title="No metrics yet" detail="Send traffic through your gateway first." />;
  }

  const { overview, by_model: byModel } = overviewQuery.data;

  return (
    <section className="page-wrap">
      <header className="page-header">
        <p className="eyebrow">Last {overview.period_days} days</p>
        <h1>Gateway Dashboard</h1>
      </header>

      <section className="metrics-grid">
        <MetricCard label="Total Requests" value={overview.total_requests.toLocaleString()} accent="amber" />
        <MetricCard label="Successful" value={overview.successful_requests.toLocaleString()} accent="teal" />
        <MetricCard label="Failed" value={overview.failed_requests.toLocaleString()} accent="rose" />
        <MetricCard label="Total Cost" value={formatUsd(overview.total_cost_usd)} accent="sky" />
      </section>

      <section className="surface-panel">
        <h2>Model Spend Snapshot</h2>
        {byModel.length === 0 ? (
          <EmptyState title="No model usage" detail="Model-level spend appears here when traffic is captured." />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Model</th>
                <th>Provider</th>
                <th>Requests</th>
                <th>Tokens</th>
                <th>Cost</th>
              </tr>
            </thead>
            <tbody>
              {byModel.slice(0, 8).map((row) => (
                <tr key={`${row.provider}-${row.model}`}>
                  <td>{row.model}</td>
                  <td>{row.provider}</td>
                  <td>{row.requests.toLocaleString()}</td>
                  <td>{row.tokens.toLocaleString()}</td>
                  <td>{formatUsd(row.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </section>
  );
}

