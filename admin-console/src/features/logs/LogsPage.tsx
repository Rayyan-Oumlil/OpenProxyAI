import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { toast } from "sonner";

import { apiClient, API_BASE_URL } from "../../api/client";
import type { Page, PolicyAnalyticsResponse, RequestLogItem, TeamResponse } from "../../api/types";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { StatusBadge, verdictForPolicyAction } from "../../components/ui/StatusBadge";
import { LogDetailDrawer } from "./LogDetailDrawer";
import { useAuth } from "../../state/AuthContext";
import { formatCost, formatLatency, formatDateTime } from "../../lib/utils";

function buildLogsPath(
  page: number,
  status: string,
  policyAction: string,
  policyReason: string,
  startDate: string,
  endDate: string,
  teamId: string,
  sessionId: string
): string {
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (status !== "all") params.set("status", status);
  if (policyAction !== "all") params.set("policy_action", policyAction);
  const r = policyReason.trim();
  if (r) params.set("policy_reason", r);
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  if (teamId) params.set("team_id", teamId);
  const s = sessionId.trim();
  if (s) params.set("session_id", s);
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
  const { token, user } = useAuth();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  const [policyActionFilter, setPolicyActionFilter] = useState("all");
  const [policyReasonFilter, setPolicyReasonFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [teamFilter, setTeamFilter] = useState("");
  const [sessionFilter, setSessionFilter] = useState("");
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);

  const teamsQuery = useQuery({
    queryKey: ["teams", token],
    queryFn: () => apiClient.get<TeamResponse[]>("/api/v1/teams", token!),
    enabled: Boolean(token) && user?.role === "admin",
  });

  const logsQuery = useQuery({
    queryKey: [
      "analytics", "logs", token, page,
      statusFilter, policyActionFilter, policyReasonFilter, startDate, endDate, teamFilter, sessionFilter,
    ],
    queryFn: () =>
      apiClient.get<Page<RequestLogItem>>(
        buildLogsPath(page, statusFilter, policyActionFilter, policyReasonFilter, startDate, endDate, teamFilter, sessionFilter),
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

  const data = logsQuery.data;
  const filtered =
    statusFilter !== "all" || policyActionFilter !== "all" || policyReasonFilter.trim() !== "" || sessionFilter.trim() !== "" ||
    startDate !== "" || endDate !== "" || teamFilter !== "";

  const columns: Column<RequestLogItem>[] = [
    { key: "time", header: "Time", nowrap: true, cell: (row) => formatDateTime(row.created_at) },
    { key: "model", header: "Model", mono: true, cell: (row) => row.model },
    {
      key: "status",
      header: "Status",
      cell: (row) => <StatusBadge verdict={row.status === "success" ? "allowed" : "blocked"}>{row.status === "success" ? "Success" : "Error"}</StatusBadge>,
    },
    {
      key: "policy",
      header: "Policy",
      cell: (row) =>
        row.policy_action ? (
          <div className="policy-cell">
            <StatusBadge verdict={verdictForPolicyAction(row.policy_action)} />
            <small>{row.policy_reason ?? "-"}</small>
          </div>
        ) : (
          <span className="text-muted">—</span>
        ),
    },
    { key: "tokens", header: "Tokens", align: "right", mono: true, cell: (row) => row.total_tokens.toLocaleString() },
    { key: "latency", header: "Latency", align: "right", mono: true, cell: (row) => (row.latency_ms != null ? formatLatency(row.latency_ms) : "—") },
    { key: "cost", header: "Cost", align: "right", mono: true, cell: (row) => formatCost(row.cost_usd) },
  ];

  return (
    <section className="page-wrap">
      <PageHeader
        title="Request logs"
        description="Every request through the gateway, with its policy decision, cost and latency."
        actions={
          <button type="button" onClick={handleExport} disabled={isExporting} className="btn-outline flex items-center gap-1.5">
            <Download size={14} aria-hidden />
            {isExporting ? "Exporting…" : "Export Policy Events CSV"}
          </button>
        }
      />

      <div className="surface-panel filters-grid">
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
          Session ID
          <input
            type="text"
            value={sessionFilter}
            placeholder="Filter by session"
            onChange={(e) => { resetPage(); setSessionFilter(e.target.value); }}
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
        {user?.role === "admin" && teamsQuery.data && teamsQuery.data.length > 0 && (
          <label className="inline-control">
            Team
            <select value={teamFilter} onChange={(e) => { resetPage(); setTeamFilter(e.target.value); }}>
              <option value="">All</option>
              {teamsQuery.data.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>


      {policyQuery.data && (
        <div className="surface-panel policy-strip">
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

      <DataTable
        caption="Request logs"
        columns={columns}
        rows={data?.items}
        getRowId={(row) => row.id}
        isLoading={logsQuery.isLoading}
        error={
          logsQuery.isError
            ? {
                title: "Unable to load logs",
                detail: logsQuery.error instanceof Error ? logsQuery.error.message : "Unknown error",
                onRetry: () => void logsQuery.refetch(),
              }
            : null
        }
        empty={
          filtered
            ? { title: "No requests match these filters", detail: "Widen the date range or clear a filter." }
            : { title: "No request logs", detail: "Send at least one request through the proxy." }
        }
        onRowClick={(row) => setSelectedLogId(row.id)}
        footer={
          data ? (
            <>
              <p className="text-muted-sm">
                Page {data.page} of {data.total_pages} &nbsp;·&nbsp; {data.total.toLocaleString()} total
              </p>
              <div className="pager-actions">
                <button type="button" onClick={() => setPage((p) => Math.max(p - 1, 1))} disabled={data.page <= 1} aria-label="Previous page">
                  Previous
                </button>
                <button type="button" onClick={() => setPage((p) => (p < data.total_pages ? p + 1 : p))} disabled={data.page >= data.total_pages} aria-label="Next page">
                  Next
                </button>
              </div>
            </>
          ) : null
        }
      />

      <LogDetailDrawer logId={selectedLogId} onClose={() => setSelectedLogId(null)} />
    </section>
  );
}
