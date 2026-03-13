import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../../api/client";
import type { Page, RequestLogItem } from "../../api/types";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { LoadingState } from "../../components/LoadingState";
import { useAuth } from "../../state/AuthContext";

function buildLogsPath(page: number, statusFilter: string): string {
  const params = new URLSearchParams({
    page: String(page),
    page_size: "20",
  });
  if (statusFilter !== "all") {
    params.set("status", statusFilter);
  }
  return `/api/v1/analytics/logs?${params.toString()}`;
}

export function LogsPage() {
  const { token } = useAuth();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");

  const logsQuery = useQuery({
    queryKey: ["analytics", "logs", token, page, statusFilter],
    queryFn: () =>
      apiClient.get<Page<RequestLogItem>>(buildLogsPath(page, statusFilter), token!),
    enabled: Boolean(token),
  });

  if (logsQuery.isLoading) {
    return <LoadingState label="Loading request logs..." />;
  }

  if (logsQuery.isError) {
    return (
      <ErrorState
        title="Unable to load logs"
        detail={logsQuery.error instanceof Error ? logsQuery.error.message : "Unknown error"}
      />
    );
  }

  if (!logsQuery.data || logsQuery.data.items.length === 0) {
    return <EmptyState title="No request logs" detail="Send at least one request through the proxy." />;
  }

  const data = logsQuery.data;

  return (
    <section className="page-wrap">
      <header className="page-header with-controls">
        <div>
          <p className="eyebrow">Traffic Inspection</p>
          <h1>Request Logs</h1>
        </div>
        <label htmlFor="status-filter" className="inline-control">
          Status
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(event) => {
              setPage(1);
              setStatusFilter(event.target.value);
            }}
          >
            <option value="all">All</option>
            <option value="success">Success</option>
            <option value="error">Error</option>
          </select>
        </label>
      </header>

      <section className="surface-panel">
        <table className="data-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Model</th>
              <th>Status</th>
              <th>Tokens</th>
              <th>Latency</th>
              <th>Cost</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((row) => (
              <tr key={row.id}>
                <td>{new Date(row.created_at).toLocaleString()}</td>
                <td>{row.model}</td>
                <td>
                  <span className={row.status === "success" ? "chip chip-success" : "chip chip-error"}>
                    {row.status}
                  </span>
                </td>
                <td>{row.total_tokens.toLocaleString()}</td>
                <td>{row.latency_ms ?? "-"} ms</td>
                <td>${row.cost_usd.toFixed(6)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <footer className="table-footer">
          <p>
            Page {data.page} of {data.total_pages}
          </p>
          <div className="pager-actions">
            <button type="button" onClick={() => setPage((prev) => Math.max(prev - 1, 1))}>
              Previous
            </button>
            <button
              type="button"
              onClick={() => setPage((prev) => (prev < data.total_pages ? prev + 1 : prev))}
            >
              Next
            </button>
          </div>
        </footer>
      </section>
    </section>
  );
}

