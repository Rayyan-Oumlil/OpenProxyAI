import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { DataTable, type Column } from "../../components/ui/DataTable";
import { useConfirm } from "../../components/ui/ConfirmDialog";
import { PageHeader } from "../../components/ui/PageHeader";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { formatDate } from "../../lib/utils";
import { useAuth } from "../../state/AuthContext";
import { AddMcpServerDialog } from "./AddMcpServerDialog";
import { McpToolsPanel } from "./McpToolsPanel";
import { mcpApi } from "./api";
import type { McpServer, PinMode, ScanMode, UpdateMcpServerRequest } from "./types";

const SERVERS_KEY = ["mcp-servers"];

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Request failed";
}

export function McpServersPage() {
  const { token } = useAuth();
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  const serversQuery = useQuery({
    queryKey: SERVERS_KEY,
    queryFn: () => mcpApi.listServers(token!),
    enabled: Boolean(token),
  });

  const create = useMutation({
    mutationFn: (data: Parameters<typeof mcpApi.createServer>[0]) => mcpApi.createServer(data, token!),
    onSuccess: (server) => {
      toast.success(`${server.name} added. Open it and press Sync now to fetch its tools.`);
      void qc.invalidateQueries({ queryKey: SERVERS_KEY });
      setShowAdd(false);
      setOpenId(server.id);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const update = useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateMcpServerRequest }) => mcpApi.updateServer(id, data, token!),
    onSuccess: () => void qc.invalidateQueries({ queryKey: SERVERS_KEY }),
    onError: (err) => toast.error(errorMessage(err)),
  });

  const remove = useMutation({
    mutationFn: (id: string) => mcpApi.deleteServer(id, token!),
    onSuccess: (_data, id) => {
      toast.success("Server removed.");
      if (openId === id) setOpenId(null);
      void qc.invalidateQueries({ queryKey: SERVERS_KEY });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const confirm = useConfirm();

  async function confirmDelete(server: McpServer) {
    const ok = await confirm({
      title: `Remove ${server.name}?`,
      description: "Its pinned tools and their history are deleted too. Agents lose access to its tools.",
      confirmLabel: "Remove server",
      destructive: true,
    });
    if (!ok) return;
    remove.mutate(server.id);
  }

  const columns: Column<McpServer>[] = [
    {
      key: "name",
      header: "Server",
      cell: (server) => (
        <div>
          <div className="dt__mono">{server.name}</div>
          <div className="mcp-tool-desc">{server.url}</div>
        </div>
      ),
    },
    {
      key: "pin",
      header: "Pinning",
      cell: (server) => (
        <select
          aria-label={`Tool pinning for ${server.name}`}
          value={server.pin_mode}
          disabled={update.isPending}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => update.mutate({ id: server.id, data: { pin_mode: e.target.value as PinMode } })}
        >
          <option value="warn">Warn</option>
          <option value="enforce">Enforce</option>
          <option value="off">Off</option>
        </select>
      ),
    },
    {
      key: "scan",
      header: "Injection scan",
      cell: (server) => (
        <select
          aria-label={`Injection scan for ${server.name}`}
          value={server.scan_mode}
          disabled={update.isPending}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => update.mutate({ id: server.id, data: { scan_mode: e.target.value as ScanMode } })}
        >
          <option value="log">Log</option>
          <option value="redact">Redact</option>
          <option value="block">Block</option>
          <option value="off">Off</option>
        </select>
      ),
    },
    { key: "auth", header: "Upstream auth", cell: (server) => (server.has_auth ? "Configured" : "None") },
    {
      key: "status",
      header: "Status",
      cell: (server) => (
        <StatusBadge verdict={server.is_active ? "allowed" : "neutral"}>{server.is_active ? "Active" : "Disabled"}</StatusBadge>
      ),
    },
    { key: "created", header: "Added", nowrap: true, cell: (server) => formatDate(server.created_at) },
    {
      key: "actions",
      header: "Actions",
      cell: (server) => (
        <div className="mcp-actions">
          <button
            type="button"
            className="btn-outline"
            disabled={update.isPending}
            onClick={(e) => {
              e.stopPropagation();
              update.mutate({ id: server.id, data: { is_active: !server.is_active } });
            }}
          >
            {server.is_active ? "Disable" : "Enable"}
          </button>
          <button
            type="button"
            className="btn-icon-only"
            aria-label={`Remove ${server.name}`}
            disabled={remove.isPending}
            onClick={(e) => {
              e.stopPropagation();
              confirmDelete(server);
            }}
          >
            <Trash2 size={15} className="text-accent-rose" aria-hidden />
          </button>
        </div>
      ),
    },
  ];

  return (
    <section className="page-wrap">
      <PageHeader
        title="MCP servers"
        description="Upstream tool servers your agents reach through /v1/mcp. Pin their tools, scan what they return, review changes."
        actions={
          <button type="button" className="bg-accent-sky" onClick={() => setShowAdd(true)}>
            <Plus size={15} aria-hidden /> Add server
          </button>
        }
      />
      <DataTable
        caption="MCP servers"
        columns={columns}
        rows={serversQuery.data}
        getRowId={(server) => server.id}
        isLoading={serversQuery.isLoading}
        error={
          serversQuery.isError
            ? {
                title: "Unable to load MCP servers",
                detail: errorMessage(serversQuery.error),
                onRetry: () => void serversQuery.refetch(),
              }
            : null
        }
        empty={{ title: "No MCP servers", detail: "Add a server to expose its tools to agents behind your policy." }}
        onRowClick={(server) => setOpenId((current) => (current === server.id ? null : server.id))}
        expandedId={openId}
        renderExpanded={(server) => <McpToolsPanel server={server} />}
        getRowLabel={(server) => server.name}
      />
      <AddMcpServerDialog
        open={showAdd}
        onClose={() => setShowAdd(false)}
        onSave={(data) => create.mutate(data)}
        isSaving={create.isPending}
      />
    </section>
  );
}
