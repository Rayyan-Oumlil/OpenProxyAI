import { useId, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, Upload } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import { Badge } from "../../components/ui/badge";
import { useConfirm } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { formatDate } from "../../lib/utils";
import { useAuth } from "../../state/AuthContext";

const PLUGINS = "/api/v1/policy-plugins";
const NAME = /^[a-z0-9]([a-z0-9_-]{0,58}[a-z0-9])?$/;

export type PolicyPlugin = {
  id: string;
  name: string;
  sha256: string;
  size_bytes: number;
  enabled: boolean;
  created_at: string;
};

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

/** The file as base64 without the data-URL prefix. */
export function toBase64(buffer: ArrayBuffer): string {
  let binary = "";
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < bytes.length; i += 0x8000)
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

export function PolicyPluginsPage() {
  const { token, user } = useAuth();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const ids = { name: useId(), file: useId() };
  const isAdmin = user?.role === "admin";
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const plugins = useQuery({
    queryKey: ["policy-plugins", token],
    queryFn: () => apiClient.get<PolicyPlugin[]>(PLUGINS, token!),
    enabled: Boolean(token) && isAdmin,
  });

  const refresh = () =>
    void qc.invalidateQueries({ queryKey: ["policy-plugins"] });
  const upload = useMutation({
    mutationFn: async () =>
      apiClient.post<PolicyPlugin>(
        PLUGINS,
        { name, module_b64: toBase64(await file!.arrayBuffer()) },
        token!,
      ),
    onSuccess: () => {
      toast.success("Plugin uploaded and enabled.");
      setName("");
      setFile(null);
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e, "Could not upload the plugin")),
  });
  const toggle = useMutation({
    mutationFn: (p: PolicyPlugin) =>
      apiClient.patch<PolicyPlugin>(
        `${PLUGINS}/${p.id}`,
        { enabled: !p.enabled },
        token!,
      ),
    onSuccess: refresh,
    onError: (e) => toast.error(errorMessage(e, "Could not change the plugin")),
  });
  const remove = useMutation({
    mutationFn: (p: PolicyPlugin) =>
      apiClient.del<void>(`${PLUGINS}/${p.id}`, token!),
    onSuccess: () => {
      toast.success("Plugin deleted.");
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e, "Could not delete the plugin")),
  });

  if (!isAdmin)
    return <p>You need admin privileges to manage policy plugins.</p>;

  const columns: Column<PolicyPlugin>[] = [
    {
      key: "name",
      header: "Name",
      cell: (p) => <span className="font-medium">{p.name}</span>,
    },
    {
      key: "status",
      header: "Status",
      cell: (p) => (
        <Badge variant={p.enabled ? "success" : "muted"}>
          {p.enabled ? "Enabled" : "Disabled"}
        </Badge>
      ),
    },
    {
      key: "hash",
      header: "SHA-256",
      mono: true,
      cell: (p) => <span title={p.sha256}>{p.sha256.slice(0, 12)}…</span>,
    },
    {
      key: "size",
      header: "Size",
      align: "right",
      mono: true,
      cell: (p) => `${p.size_bytes.toLocaleString()} B`,
    },
    {
      key: "created",
      header: "Uploaded",
      nowrap: true,
      cell: (p) => formatDate(p.created_at),
    },
    {
      key: "actions",
      header: "Actions",
      cell: (p) => (
        <div className="flex gap-2">
          <button
            type="button"
            className="btn-outline btn-small"
            onClick={() => toggle.mutate(p)}
          >
            {p.enabled ? "Disable" : "Enable"}
          </button>
          <button
            type="button"
            className="btn-icon-only"
            aria-label={`Delete plugin ${p.name}`}
            onClick={async () => {
              if (
                await confirm({
                  title: "Delete plugin?",
                  description: `“${p.name}” stops being applied to requests straight away.`,
                  confirmLabel: "Delete plugin",
                  destructive: true,
                })
              )
                remove.mutate(p);
            }}
          >
            <Trash2 size={14} aria-hidden="true" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="page">
      <PageHeader
        title="Policy plugins"
        description="Add your own rule to the policy check as a sandboxed WebAssembly module. A plugin can only add a restriction; one that fails blocks under enforce."
      />
      <form
        className="stack-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (!NAME.test(name))
            return toast.error(
              "Use lowercase letters, digits, - and _ for the name.",
            );
          if (!file) return toast.error("Choose a .wasm file.");
          upload.mutate();
        }}
      >
        <h2>Upload a plugin</h2>
        <div className="composer__row">
          <label className="inline-control" htmlFor={ids.name}>
            Name
            <input
              id={ids.name}
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={60}
              placeholder="e.g. no-codenames"
            />
          </label>
          <label className="inline-control" htmlFor={ids.file}>
            WebAssembly file
            <input
              id={ids.file}
              type="file"
              accept=".wasm,application/wasm"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
        </div>
        <p className="text-muted text-sm">
          It is checked before it is stored: no imports (a plugin can call
          nothing), the three required exports, and a test call. At most 5
          plugins, 1 MB each.
        </p>
        <div>
          <button
            type="submit"
            className="bg-accent-sky"
            disabled={upload.isPending}
          >
            <Upload size={14} aria-hidden="true" />{" "}
            {upload.isPending ? "Uploading…" : "Upload plugin"}
          </button>
        </div>
      </form>
      <DataTable
        caption="Policy plugins"
        columns={columns}
        rows={plugins.data}
        getRowId={(p) => p.id}
        isLoading={plugins.isLoading}
        error={
          plugins.isError
            ? {
                title: "Could not load plugins",
                detail: errorMessage(plugins.error, "Unknown error"),
                onRetry: () => void plugins.refetch(),
              }
            : null
        }
        empty={{
          title: "No plugins",
          detail: "Upload a module to add your own rule to the policy check.",
        }}
      />
    </div>
  );
}
