import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type { Page, PolicyAnalyticsResponse, RequestLogItem } from "../../api/types";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { LoadingState } from "../../components/LoadingState";
import { LogDetailDrawer } from "./LogDetailDrawer";
import { useAuth } from "../../state/AuthContext";
import { formatCost, formatLatency } from "../../lib/utils";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function buildLogsPath(
  page: number,
  status: string,
  policyAction: string,
  policyReason: string,
  startDate: string,
  endDate: string
): string {
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (status !== "all") params.set("status", status);
  if (policyAction !== "all") params.set("policy_action", policyAction);
  const r = policyReason.trim();
  if (r) params.set("policy_reason", r);
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  return `/api/v1/analytics/logs?${params.toString()}`;
}

async function downloadCsv(
  token: string,
  policyAction: string,
  startDate: string,
  endDate: string
) {
  const params = new URLSearchParams({ format: "csv" });
  if (policyAction !== "all") params.set("policy_action", policyAction);
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);

  const res = await fetch(
    `${API_BASE_URL}/api/v1/analytics/policy/export?${params.toString()}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );

  if (!res.ok) throw new Error(`Export failed: ${res.status}`);

  const truncated = res.headers.get("X-Result-Truncated") === "true";
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `policy-events-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);

  if (truncated) {
    toast.warning("Export limited to 10,000 rows. Refine your filters for a smaller range.");
  } else {
    toast.success("CSV export downloaded.");
  }
}

export function LogsPage() {
  const { token } = useAuth();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  const [policyActionFilter, setPolicyActionFilter] = useState("all");
  const [policyReasonFilter, setPolicyReasonFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);

  const logsQuery = useQuery({
    queryKey: [
      "analytics", "logs", token, page,
      statusFilter, policyActionFilter, policyReasonFilter, startDate, endDate,
    ],
    queryFn: () =>
      apiClient.get<Page<RequestLogItem>>(
        buildLogsPath(page, statusFilter, policyActionFilter, policyReasonFilter, startDate, endDate),
        token!
      ),
    enabled: Boolean(token),
  });

  const policyQuery = useQuery({
    queryKey: ["analytics", "policy", token],
    queryFn: () =>
      apiClient.get<PolicyAnalyticsResponse>("/api/v1/analytics/policy?period_days=30", token!),
    enabled: Boolean(token),
  });

  function resetPage() { setPage(1); }

  async function handleExport() {
    if (!token) return;
    setIsExporting(true);
    try {
      await downloadCsv(token, policyActionFilter, startDate, endDate);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Export failed");
    } finally {
      setIsExporting(false);
    }
  }

  if (logsQuery.isLoading) return <LoadingState label="Loading request logs..." />;
  if (logsQuery.isError)
    return (
      <ErrorState
        title="Unable to load logs"
        detail={logsQuery.error instanceof Error ? logsQuery.error.message : "Unknown error"}
      />
    );
  if (!logsQuery.data || logsQuery.data.items.length === 0)
    return <EmptyState title="No request logs" detail="Send at least one request through the proxy." />;

  const data = logsQuery.data;

  return (
    <section className="page-wrap">
      <header className="page-header with-controls">
        <div>
          <p className="eyebrow">Traffic Inspection</p>
          <h1>Request Logs</h1>
        </div>
        <button
          type="button"
          onClick={handleExport}
          disabled={isExporting}
          className="flex items-center gap-1.5 text-sm px-3 py-2 rounded-lg transition-colors"
          style={{ border: "1px solid var(--line)", background: "transparent", color: "var(--text)" }}
        >
          <Download size={14} />
          {isExporting ? "Exporting…" : "Export CSV"}
        </button>
      </header>

      <div
        className="surface-panel grid gap-3"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))" }}
      >
        <label className="inline-control">
          Status
          <select value={statusFilter} onChange={(e) => { resetPage(); setStatusFilter(e.target.value); }}>
            <option value="all">All</option>
            <option value="success">Success</option>
            <option value="error">Error</option>
          </select>
        </label>
        <label className="inline-control">
          Policy Action
          <select value={policyActionFilter} onChange={(e) => { resetPage(); setPolicyActionFilter(e.target.value); }}>
            <option value="all">All</option>
            <option value="allow">Allow</option>
            <option value="log_only">Log Only</option>
            <option value="block">Block</option>
          </select>
        </label>
        <label className="inline-control">
          Policy Reason
          <input
            type="text"
            value={policyReasonFilter}
            placeholder="e.g. blocked_keyword"
            onChange={(e) => { resetPage(); setPolicyReasonFilter(e.target.value); }}
          />
        </label>
        <label className="inline-control">
          From
          <input type="date" value={startDate} onChange={(e) => { resetPage(); setStartDate(e.target.value); }} />
        </label>
        <label className="inline-control">
          To
          <input type="date" value={endDate} onChange={(e) => { resetPage(); setEndDate(e.target.value); }} />
        </label>
      </div>

      <section className="surface-panel">
        {policyQuery.data && (
          <div className="policy-strip">
            <strong>Policy events (30d): {policyQuery.data.total_policy_events.toLocaleString()}</strong>
            <div className="policy-strip-actions">
              {policyQuery.data.by_action.map((entry) => (
                <span key={entry.action} className="chip chip-policy">
                  {entry.action}: {entry.count}
                </span>
              ))}
            </div>
          </div>
        )}

        <table className="data-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Model</th>
              <th>Status</th>
              <th>Policy</th>
              <th>Tokens</th>
              <th>Latency</th>
              <th>Cost</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((row) => (
              <tr
                key={row.id}
                onClick={() => setSelectedLogId(row.id)}
                style={{ cursor: "pointer" }}
                className="hover:bg-[rgba(44,109,191,0.04)] transition-colors"
              >
                <td style={{ fontSize: "0.82rem", color: "var(--muted)" }}>
                  {new Date(row.created_at).toLocaleString()}
                </td>
                <td style={{ fontSize: "0.88rem" }}>{row.model}</td>
                <td>
                  <span className={row.status === "success" ? "chip chip-success" : "chip chip-error"}>
                    {row.status}
                  </span>
                </td>
                <td>
                  {row.policy_action ? (
                    <div className="policy-cell">
                      <span className="chip chip-policy">{row.policy_action}</span>
                      <small>{row.policy_reason ?? "-"}</small>
                    </div>
                  ) : (
                    <span style={{ color: "var(--muted)" }}>—</span>
                  )}
                </td>
                <td>{row.total_tokens.toLocaleString()}</td>
                <td>{row.latency_ms != null ? formatLatency(row.latency_ms) : "—"}</td>
                <td>{formatCost(row.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <footer className="table-footer">
          <p style={{ color: "var(--muted)", fontSize: "0.88rem" }}>
            Page {data.page} of {data.total_pages} &nbsp;·&nbsp; {data.total.toLocaleString()} total
          </p>
          <div className="pager-actions">
            <button type="button" onClick={() => setPage((p) => Math.max(p - 1, 1))} disabled={data.page <= 1}>
              Previous
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => (p < data.total_pages ? p + 1 : p))}
              disabled={data.page >= data.total_pages}
            >
              Next
            </button>
          </div>
        </footer>
      </section>

      <LogDetailDrawer logId={selectedLogId} onClose={() => setSelectedLogId(null)} />
    </section>
  );
}
