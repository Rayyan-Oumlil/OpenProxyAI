import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { DataTable, type Column } from "../../components/ui/DataTable";
import { StatusBadge, type Verdict } from "../../components/ui/StatusBadge";
import { formatDate } from "../../lib/utils";
import { useAuth } from "../../state/AuthContext";
import { mcpApi } from "./api";
import { changedFields } from "./toolDiff";
import type { McpServer, McpTool, ToolStatus } from "./types";

const VERDICT: Record<ToolStatus, Verdict> = {
  approved: "allowed",
  pending: "pending",
  drifted: "drifted",
  blocked: "blocked",
};

const STATUS_LABEL: Record<ToolStatus, string> = {
  approved: "Approved",
  pending: "Pending review",
  drifted: "Drifted",
  blocked: "Blocked",
};

const PIN_HELP = {
  enforce: "Enforce: only approved tools are visible and callable.",
  warn: "Warn: the first definition is trusted, later changes are flagged as drifted.",
  off: "Pinning is off: tool definitions are served live.",
} as const;

function description(tool: McpTool): string {
  const text = (tool.approved_snapshot ?? tool.definition).description;
  return typeof text === "string" ? text : "";
}

function Drift({ tool }: { tool: McpTool }) {
  const changes = changedFields(tool);
  if (tool.status !== "drifted" || changes.length === 0) return null;
  return (
    <div className="mcp-drift" role="group" aria-label={`Changes to ${tool.name} since approval`}>
      <p className="mcp-drift__title">Changed since approval. Agents still see the approved version.</p>
      {changes.map((change) => (
        <div key={change.field} className="mcp-drift__field">
          <strong>{change.field}</strong>
          <pre className="mcp-drift__old" aria-label={`Approved ${change.field}`}>{change.approved}</pre>
          <pre className="mcp-drift__new" aria-label={`Live ${change.field}`}>{change.live}</pre>
        </div>
      ))}
    </div>
  );
}

export function McpToolsPanel({ server }: { server: McpServer }) {
  const { token } = useAuth();
  const qc = useQueryClient();
  const key = ["mcp-tools", server.id];

  const toolsQuery = useQuery({
    queryKey: key,
    queryFn: () => mcpApi.listTools(server.id, token!),
    enabled: Boolean(token),
  });

  const onError = (err: unknown) => toast.error(err instanceof Error ? err.message : "Request failed");

  const sync = useMutation({
    mutationFn: () => mcpApi.syncTools(server.id, token!),
    onSuccess: (tools) => {
      qc.setQueryData(key, tools);
      toast.success("Tool list refreshed from the server.");
    },
    onError,
  });

  const review = useMutation({
    mutationFn: ({ tool, action }: { tool: McpTool; action: "approve" | "block" }) =>
      mcpApi.reviewTool(server.id, tool.id, action, token!),
    onSuccess: (updated) => {
      qc.setQueryData<McpTool[]>(key, (tools) => tools?.map((t) => (t.id === updated.id ? updated : t)));
      toast.success(`${updated.name} is now ${updated.status}.`);
    },
    onError,
  });

  const columns: Column<McpTool>[] = [
    {
      key: "name",
      header: "Tool",
      cell: (tool) => (
        <div>
          <div className="dt__mono">{tool.name}</div>
          <div className="mcp-tool-desc">{description(tool) || "No description"}</div>
          <Drift tool={tool} />
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (tool) => <StatusBadge verdict={VERDICT[tool.status]}>{STATUS_LABEL[tool.status]}</StatusBadge>,
    },
    { key: "seen", header: "Last seen", nowrap: true, cell: (tool) => formatDate(tool.last_seen_at) },
    {
      key: "actions",
      header: "Review",
      cell: (tool) => (
        <div className="mcp-actions">
          {tool.status !== "approved" ? (
            <button
              type="button"
              className="btn-outline"
              disabled={review.isPending}
              onClick={() => review.mutate({ tool, action: "approve" })}
              aria-label={`${tool.status === "blocked" ? "Unblock and approve" : "Approve"} ${tool.name}`}
            >
              {tool.status === "blocked" ? "Unblock" : "Approve"}
            </button>
          ) : null}
          {tool.status !== "blocked" ? (
            <button
              type="button"
              className="btn-outline"
              disabled={review.isPending}
              onClick={() => review.mutate({ tool, action: "block" })}
              aria-label={`Block ${tool.name}`}
            >
              Block
            </button>
          ) : null}
        </div>
      ),
    },
  ];

  return (
    <div className="mcp-tools">
      <div className="mcp-tools__bar">
        <p>{PIN_HELP[server.pin_mode]}</p>
        <button type="button" className="btn-outline" disabled={sync.isPending} onClick={() => sync.mutate()}>
          <RefreshCw size={14} aria-hidden /> {sync.isPending ? "Syncing…" : "Sync now"}
        </button>
      </div>
      <DataTable
        caption={`Tools of ${server.name}`}
        columns={columns}
        rows={toolsQuery.data}
        getRowId={(tool) => tool.id}
        isLoading={toolsQuery.isLoading}
        error={
          toolsQuery.isError
            ? {
                title: "Unable to load tools",
                detail: toolsQuery.error instanceof Error ? toolsQuery.error.message : "Unknown error",
                onRetry: () => void toolsQuery.refetch(),
              }
            : null
        }
        empty={{ title: "No tools yet", detail: "Press Sync now to fetch the tool list from the server." }}
        density="compact"
        skeletonRows={3}
      />
    </div>
  );
}
