import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";

import { apiClient } from "../../api/client";
import type { AdminAuditLogEntry, Page } from "../../api/types";
import { formatDateTime, formatNumber } from "../../lib/utils";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { useAuth } from "../../state/AuthContext";

// ── Action badge colors ──────────────────────────────────────────────────────

type ActionCategory = "policy" | "user" | "provider_key" | "invite" | "default";

function getActionCategory(action: string): ActionCategory {
  if (action.startsWith("policy")) return "policy";
  if (action.startsWith("user")) return "user";
  if (action.startsWith("provider_key")) return "provider_key";
  if (action.startsWith("invite")) return "invite";
  return "default";
}

const ACTION_BADGE_STYLES: Record<ActionCategory, React.CSSProperties> = {
  policy: { background: "color-mix(in srgb, var(--accent) 14%, transparent)", color: "var(--accent)" },
  user: { background: "color-mix(in srgb, var(--warn) 14%, transparent)", color: "var(--warn)" },
  provider_key: { background: "color-mix(in srgb, var(--drift) 14%, transparent)", color: "var(--drift)" },
  invite: { background: "color-mix(in srgb, var(--ok) 14%, transparent)", color: "var(--ok)" },
  default: { background: "var(--bg-sunken)", color: "var(--muted)" },
};

function ActionBadge({ action }: { action: string }) {
  const category = getActionCategory(action);
  return (
    <span
      className="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium"
      style={ACTION_BADGE_STYLES[category]}
    >
      {action}
    </span>
  );
}

// ── Before/After diff panel ──────────────────────────────────────────────────

function JsonPanel({ label, data }: { label: string; data: Record<string, unknown> | null }) {
  if (!data) {
    return (
      <div className="flex flex-col gap-1" style={{ flex: "1 1 240px", minWidth: 0 }}>
        <p style={{ fontSize: "var(--text-xs)", fontWeight: 500, color: "var(--muted)" }}>
          {label}
        </p>
        <p style={{ fontSize: "0.82rem", color: "var(--muted)" }}>—</p>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1" style={{ flex: "1 1 240px", minWidth: 0 }}>
      <p style={{ fontSize: "var(--text-xs)", fontWeight: 500, color: "var(--muted)" }}>
        {label}
      </p>
      <pre
        style={{
          background: "var(--bg)",
          border: "1px solid var(--line)",
          borderRadius: 6,
          padding: "0.5rem 0.75rem",
          fontSize: "0.75rem",
          overflow: "auto",
          maxHeight: 200,
          fontFamily: "JetBrains Mono, Fira Code, monospace",
          whiteSpace: "pre-wrap",
          wordBreak: "break-all",
          margin: 0,
        }}
      >
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}

// ── Detail expanded row ──────────────────────────────────────────────────────

function hasDetail(row: AdminAuditLogEntry): boolean {
  return row.before !== null || row.after !== null || row.resource_id !== null;
}

function DetailPanel({ entry }: { entry: AdminAuditLogEntry }) {
  return (
    <div>
      <div className="flex flex-wrap gap-4">
        <JsonPanel label="Before" data={entry.before} />
        <JsonPanel label="After" data={entry.after} />
      </div>
      {entry.resource_id && (
        <p style={{ marginTop: "0.5rem", fontSize: "var(--text-sm)", color: "var(--muted)" }}>
          Resource ID: <code>{entry.resource_id}</code>
        </p>
      )}
    </div>
  );
}

// ── URL builder ─────────────────────────────────────────────────────────────

function buildAuditPath(page: number, action: string, resourceType: string): string {
  const params = new URLSearchParams({ page: String(page), page_size: "50" });
  if (action) params.set("action", action);
  if (resourceType) params.set("resource_type", resourceType);
  return `/api/v1/admin/audit-log?${params.toString()}`;
}

// ── Main page ────────────────────────────────────────────────────────────────

export function AuditLogPage() {
  const { token, user } = useAuth();
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");
  const [resourceTypeFilter, setResourceTypeFilter] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["admin-audit-log", token, page, actionFilter, resourceTypeFilter],
    queryFn: () =>
      apiClient.get<Page<AdminAuditLogEntry>>(
        buildAuditPath(page, actionFilter, resourceTypeFilter),
        token!
      ),
    enabled: Boolean(token) && user?.role === "admin",
  });

  // Guard: non-admins redirect to dashboard
  if (user && user.role !== "admin") {
    return (
      <Navigate to="/" replace />
    );
  }

  function resetPage() {
    setPage(1);
  }

  const data = query.data;

  const columns: Column<AdminAuditLogEntry>[] = [
    { key: "when", header: "When", nowrap: true, cell: (row) => <span className="text-muted-sm">{formatDateTime(row.created_at)}</span> },
    { key: "actor", header: "Actor", cell: (row) => row.actor_email },
    { key: "action", header: "Action", cell: (row) => <ActionBadge action={row.action} /> },
    { key: "resource", header: "Resource", cell: (row) => row.resource_type },
    { key: "ip", header: "IP address", mono: true, cell: (row) => row.ip_address ?? "\u2014" },
  ];

  return (
    <section className="page-wrap">
      <PageHeader title="Audit log" description="Every change an admin makes to policy, keys and users, with who made it and from where." />

      <div className="surface-panel filters-grid">
        <label className="inline-control">
          Action
          <input
            type="text"
            value={actionFilter}
            placeholder="policy.update"
            onChange={(e) => {
              resetPage();
              setActionFilter(e.target.value.trim());
            }}
          />
        </label>
        <label className="inline-control">
          Resource type
          <input
            type="text"
            value={resourceTypeFilter}
            placeholder="provider_key"
            onChange={(e) => {
              resetPage();
              setResourceTypeFilter(e.target.value.trim());
            }}
          />
        </label>
      </div>

      <DataTable
        caption="Admin audit log"
        columns={columns}
        rows={data?.items}
        getRowId={(row) => row.id}
        isLoading={query.isLoading}
        error={
          query.isError
            ? {
                title: "Could not load the audit log",
                detail: query.error instanceof Error ? query.error.message : "The server did not respond.",
                onRetry: () => void query.refetch(),
              }
            : null
        }
        empty={{
          title: "No audit entries yet",
          detail: "Policy changes, user updates and provider key edits show up here as admins make them.",
        }}
        isRowInteractive={hasDetail}
        onRowClick={(row) => setExpandedId(expandedId === row.id ? null : row.id)}
        expandedId={expandedId}
        renderExpanded={(row) => <DetailPanel entry={row} />}
        getRowLabel={(row) => `${row.action} by ${row.actor_email}`}
        footer={
          data ? (
            <>
              <span>
                Page {formatNumber(data.page)} of {formatNumber(data.total_pages)} &middot; {formatNumber(data.total)} entries
              </span>
              <div className="pager">
                <button type="button" className="btn-outline" onClick={() => setPage((p) => Math.max(p - 1, 1))} disabled={data.page <= 1}>
                  Previous
                </button>
                <button
                  type="button"
                  className="btn-outline"
                  onClick={() => setPage((p) => (p < data.total_pages ? p + 1 : p))}
                  disabled={data.page >= data.total_pages}
                >
                  Next
                </button>
              </div>
            </>
          ) : null
        }
      />
    </section>
  );
}
