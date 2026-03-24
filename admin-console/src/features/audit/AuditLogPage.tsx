import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { Navigate } from "react-router-dom";

import { apiClient } from "../../api/client";
import type { AdminAuditLogEntry, Page } from "../../api/types";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { LoadingState } from "../../components/LoadingState";
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
  policy: { background: "rgba(14,165,233,0.1)", color: "#0369a1" },
  user: { background: "rgba(245,158,11,0.1)", color: "#92400e" },
  provider_key: { background: "rgba(124,58,237,0.1)", color: "#5b21b6" },
  invite: { background: "rgba(20,184,166,0.1)", color: "#0f766e" },
  default: { background: "rgba(100,116,139,0.08)", color: "var(--muted)" },
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
      <div className="flex flex-col gap-1" style={{ flex: 1 }}>
        <p style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          {label}
        </p>
        <p style={{ fontSize: "0.82rem", color: "var(--muted)" }}>—</p>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1" style={{ flex: 1 }}>
      <p style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
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

function DetailRow({ entry }: { entry: AdminAuditLogEntry }) {
  return (
    <tr>
      <td colSpan={5} style={{ padding: "0.75rem 1rem", background: "rgba(44,109,191,0.03)" }}>
        <div className="flex gap-4">
          <JsonPanel label="Before" data={entry.before} />
          <JsonPanel label="After" data={entry.after} />
        </div>
        {entry.resource_id && (
          <p style={{ marginTop: "0.5rem", fontSize: "0.78rem", color: "var(--muted)" }}>
            Resource ID: <code style={{ fontSize: "0.75rem" }}>{entry.resource_id}</code>
          </p>
        )}
      </td>
    </tr>
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

  if (query.isLoading) return <LoadingState label="Loading audit log..." />;
  if (query.isError)
    return (
      <ErrorState
        title="Unable to load audit log"
        detail={query.error instanceof Error ? query.error.message : "Unknown error"}
      />
    );

  const data = query.data;

  return (
    <section className="page-wrap">
      <header className="page-header">
        <div>
          <p className="eyebrow">Security &amp; Compliance</p>
          <h1 className="flex items-center gap-2">
            <ShieldCheck size={22} style={{ color: "var(--accent-sky)" }} />
            Audit Log
          </h1>
        </div>
      </header>

      {/* Filter bar */}
      <div
        className="surface-panel grid gap-3"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))" }}
      >
        <label className="inline-control">
          Action
          <input
            type="text"
            value={actionFilter}
            placeholder="e.g. policy.update"
            onChange={(e) => {
              resetPage();
              setActionFilter(e.target.value.trim());
            }}
          />
        </label>
        <label className="inline-control">
          Resource Type
          <input
            type="text"
            value={resourceTypeFilter}
            placeholder="e.g. provider_key"
            onChange={(e) => {
              resetPage();
              setResourceTypeFilter(e.target.value.trim());
            }}
          />
        </label>
      </div>

      {/* Table or empty state */}
      {!data || data.items.length === 0 ? (
        <EmptyState
          title="No audit entries yet"
          detail="Admin actions (policy changes, user updates, provider key edits) will appear here."
        />
      ) : (
        <section className="surface-panel">
          <table className="data-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Resource</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => {
                const isExpanded = expandedId === row.id;
                const hasDetail = row.before !== null || row.after !== null || row.resource_id !== null;
                return (
                  <Fragment key={row.id}>
                    <tr
                      onClick={() => hasDetail && setExpandedId(isExpanded ? null : row.id)}
                      style={{ cursor: hasDetail ? "pointer" : "default" }}
                      className="hover:bg-[rgba(44,109,191,0.04)] transition-colors"
                    >
                      <td style={{ fontSize: "0.82rem", color: "var(--muted)", whiteSpace: "nowrap" }}>
                        {new Date(row.created_at).toLocaleString()}
                      </td>
                      <td style={{ fontSize: "0.85rem" }}>{row.actor_email}</td>
                      <td>
                        <ActionBadge action={row.action} />
                      </td>
                      <td style={{ fontSize: "0.85rem" }}>{row.resource_type}</td>
                      <td style={{ fontSize: "0.82rem", color: "var(--muted)" }}>
                        {row.ip_address ?? "—"}
                      </td>
                    </tr>
                    {isExpanded && <DetailRow key={`${row.id}-detail`} entry={row} />}
                  </Fragment>
                );
              })}
            </tbody>
          </table>

          <footer className="table-footer">
            <p style={{ color: "var(--muted)", fontSize: "0.88rem" }}>
              Page {data.page} of {data.total_pages}&nbsp;·&nbsp;
              {data.total.toLocaleString()} total
            </p>
            <div className="pager-actions">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
                disabled={data.page <= 1}
              >
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
      )}
    </section>
  );
}
