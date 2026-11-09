import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, ToggleLeft, ToggleRight, Plug2 } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type {
  DataClass,
  ProviderKeyResponse,
  CreateProviderKeyRequest,
  UpdateProviderKeyRequest,
} from "../../api/types";
import { Badge } from "../../components/ui/badge";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { useConfirm } from "../../components/ui/ConfirmDialog";
import { DATA_CLASSES, dataClassLabel } from "../../lib/dataClasses";
import { formatDate } from "../../lib/utils";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "../../components/ui/dialog";
import { useAuth } from "../../state/AuthContext";

const PROVIDERS = [
  "openai",
  "anthropic",
  "azure",
  "mistral",
  "cohere",
  "gemini",
  "groq",
  "together_ai",
  "ollama",
  "other",
];

const REGIONS = [
  { value: "us", label: "US" },
  { value: "eu", label: "EU" },
  { value: "ap", label: "Asia-Pacific" },
  { value: "global", label: "Global" },
] as const;

/** Custom endpoints go through a connection guard that only wraps OpenAI-compatible servers, so only this provider offers one. */
const CUSTOM_ENDPOINT_PROVIDER = "openai";

/** The host is enough to recognise an endpoint in a table; the full URL stays in the tooltip. */
function endpointHost(apiBase: string): string {
  try {
    return new URL(apiBase).host;
  } catch {
    return apiBase;
  }
}

function AddKeyModal({
  open,
  onClose,
  onSave,
  isSaving,
}: {
  open: boolean;
  onClose: () => void;
  onSave: (data: CreateProviderKeyRequest) => void;
  isSaving: boolean;
}) {
  const [provider, setProvider] = useState("openai");
  const [alias, setAlias] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [weight, setWeight] = useState("1.0");
  const [region, setRegion] = useState<"us" | "eu" | "ap" | "global">("us");
  const [apiBase, setApiBase] = useState("");
  const [maxDataClass, setMaxDataClass] = useState<DataClass>("internal");
  const [isInternal, setIsInternal] = useState(false);

  const supportsEndpoint = provider === CUSTOM_ENDPOINT_PROVIDER;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!apiKey.trim()) {
      toast.error("API key is required.");
      return;
    }
    onSave({
      provider,
      key_alias: alias.trim() || provider,
      api_key: apiKey.trim(),
      weight: parseFloat(weight) || 1.0,
      region,
      ...(supportsEndpoint && apiBase.trim() ? { api_base: apiBase.trim() } : {}),
      max_data_class: maxDataClass,
      is_internal: supportsEndpoint && isInternal,
    });
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Provider Key</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="stack-form">
          <label className="inline-control">
            Provider
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              {PROVIDERS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <label className="inline-control">
            Alias
            <input
              type="text"
              value={alias}
              onChange={(e) => setAlias(e.target.value)}
              placeholder="e.g. Production OpenAI"
            />
          </label>
          <label className="inline-control">
            API Key
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
              required
              autoComplete="new-password"
            />
          </label>
          <label className="inline-control">
            Weight
            <input
              type="number"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              min="0.1"
              max="10"
              step="0.1"
            />
          </label>
          <label className="inline-control">
            Region
            <select value={region} onChange={(e) => setRegion(e.target.value as "us" | "eu" | "ap" | "global")}>
              {REGIONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
          {supportsEndpoint ? (
            <label className="inline-control">
              Custom endpoint (optional): any OpenAI-compatible server, such as vLLM or Ollama's /v1
              <input
                type="url"
                value={apiBase}
                onChange={(e) => setApiBase(e.target.value)}
                placeholder="https://vllm.example.com/v1"
                autoComplete="off"
              />
            </label>
          ) : null}
          <label className="inline-control">
            Most sensitive data this endpoint may receive
            <select value={maxDataClass} onChange={(e) => setMaxDataClass(e.target.value as DataClass)}>
              {DATA_CLASSES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
          {supportsEndpoint ? (
            <label className="inline-control">
              <span>
                <input type="checkbox" checked={isInternal} onChange={(e) => setIsInternal(e.target.checked)} /> The endpoint is inside my own network
              </span>
            </label>
          ) : null}
          <DialogFooter>
            <button type="button" onClick={onClose} className="btn-outline">
              Cancel
            </button>
            <button type="submit" disabled={isSaving} className="bg-accent-sky">
              {isSaving ? "Saving…" : "Add Key"}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ProviderKeysPage() {
  const { token } = useAuth();
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [regionFilter, setRegionFilter] = useState<string>("all");

  const keysQuery = useQuery({
    queryKey: ["provider-keys", token],
    queryFn: () => apiClient.get<ProviderKeyResponse[]>("/api/v1/provider-keys", token!),
    enabled: Boolean(token),
  });

  const addMutation = useMutation({
    mutationFn: (data: CreateProviderKeyRequest) =>
      apiClient.post<ProviderKeyResponse>("/api/v1/provider-keys", data, token!),
    onSuccess: () => {
      toast.success("Provider key added.");
      qc.invalidateQueries({ queryKey: ["provider-keys"] });
      setShowAdd(false);
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to add key"),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      apiClient.patch<ProviderKeyResponse>(
        `/api/v1/provider-keys/${id}`,
        { is_active } satisfies UpdateProviderKeyRequest,
        token!
      ),
    onSuccess: () => {
      toast.success("Key updated.");
      qc.invalidateQueries({ queryKey: ["provider-keys"] });
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to update key"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      apiClient.del(`/api/v1/provider-keys/${id}`, token!),
    onSuccess: () => {
      toast.success("Key deleted.");
      qc.invalidateQueries({ queryKey: ["provider-keys"] });
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to delete key"),
  });

  const confirm = useConfirm();

  async function handleDelete(id: string) {
    const ok = await confirm({
      title: "Delete provider key?",
      description: "Requests that rely on this key will fall back to other keys or fail. This action cannot be undone.",
      confirmLabel: "Delete key",
      destructive: true,
    });
    if (!ok) return;
    deleteMutation.mutate(id);
  }

  const keys = keysQuery.data ?? [];
  const filteredKeys = regionFilter === "all" ? keys : keys.filter((k) => k.region === regionFilter);
  // Adaptive load-balancing columns only exist when some key reports them.
  const showAdaptive = keys.some((k) => k.effective_weight != null || k.latency_p99_ms != null);
  // Circuit expiry is judged against when the data was fetched, so rendering stays pure.
  const nowSeconds = keysQuery.dataUpdatedAt / 1000;

  const adaptiveColumns: Column<ProviderKeyResponse>[] = showAdaptive
    ? [
        { key: "p99", header: "P99 (ms)", align: "right", mono: true, cell: (k) => (k.latency_p99_ms != null ? Math.round(k.latency_p99_ms) : "—") },
        { key: "errors", header: "Error %", align: "right", mono: true, cell: (k) => (k.error_rate != null ? `${(k.error_rate * 100).toFixed(1)}%` : "—") },
        { key: "effective", header: "Eff. weight", align: "right", mono: true, cell: (k) => (k.effective_weight != null ? k.effective_weight : "—") },
      ]
    : [];

  const columns: Column<ProviderKeyResponse>[] = [
    {
      key: "provider",
      header: "Provider",
      cell: (k) => (
        <span className="flex items-center gap-1.5">
          <Plug2 size={13} className="text-muted" aria-hidden />
          {k.provider}
        </span>
      ),
    },
    { key: "alias", header: "Alias", cell: (k) => k.key_alias ?? k.alias ?? "—" },
    {
      key: "region",
      header: "Region",
      cell: (k) => (
        <Badge variant="muted" className="text-xs">
          {REGIONS.find((r) => r.value === k.region)?.label ?? k.region ?? "US"}
        </Badge>
      ),
    },
    {
      key: "endpoint",
      header: "Endpoint",
      cell: (k) =>
        k.api_base ? (
          <span title={k.api_base} className="flex items-center gap-1.5">
            {endpointHost(k.api_base)}
            {k.is_internal ? <Badge variant="muted" className="text-xs">Private network</Badge> : null}
          </span>
        ) : (
          <span className="text-muted text-xs">Provider default</span>
        ),
    },
    {
      key: "dataclass",
      header: "Max data class",
      cell: (k) => (
        <Badge variant="muted" className="text-xs">
          {dataClassLabel(k.max_data_class ?? "internal")}
        </Badge>
      ),
    },
    { key: "prefix", header: "Key prefix", mono: true, cell: (k) => `${k.key_prefix}…` },
    { key: "weight", header: "Weight", align: "right", mono: true, cell: (k) => k.weight },
    ...adaptiveColumns,
    {
      key: "circuit",
      header: "Circuit",
      cell: (k) =>
        k.circuit_open_until != null && k.circuit_open_until > nowSeconds ? (
          <Badge variant="warning" title={`Open until ${new Date(k.circuit_open_until * 1000).toLocaleString()}`}>
            Open
          </Badge>
        ) : (
          <span className="text-muted text-xs">Closed</span>
        ),
    },
    {
      key: "status",
      header: "Status",
      cell: (k) => <Badge variant={k.is_active ? "success" : "muted"}>{k.is_active ? "Active" : "Inactive"}</Badge>,
    },
    { key: "created", header: "Created", nowrap: true, cell: (k) => formatDate(k.created_at) },
    {
      key: "actions",
      header: "Actions",
      cell: (k) => (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => toggleMutation.mutate({ id: k.id, is_active: !k.is_active })}
            className="btn-icon-only"
            aria-label={k.is_active ? `Deactivate ${k.key_alias ?? k.provider}` : `Activate ${k.key_alias ?? k.provider}`}
          >
            {k.is_active ? <ToggleRight size={18} className="text-accent-teal" aria-hidden /> : <ToggleLeft size={18} className="text-muted" aria-hidden />}
          </button>
          <button type="button" onClick={() => void handleDelete(k.id)} className="btn-icon-only" aria-label={`Delete ${k.key_alias ?? k.provider}`}>
            <Trash2 size={14} className="text-accent-rose" aria-hidden />
          </button>
        </div>
      ),
    },
  ];

  return (
    <section className="page-wrap">
      <PageHeader
        title="Provider keys"
        description="The LLM provider credentials the gateway routes traffic through."
        actions={
          <button type="button" onClick={() => setShowAdd(true)} className="flex items-center gap-1.5 bg-accent-sky" aria-label="Add provider key">
            <Plus size={15} aria-hidden />
            Add Provider Key
          </button>
        }
      />

      <div className="flex items-center gap-2 mb-3">
        <label htmlFor="region-filter" className="text-muted-sm font-medium">
          Filter by region:
        </label>
        <select
          id="region-filter"
          value={regionFilter}
          onChange={(e) => setRegionFilter(e.target.value)}
          className="select-filter"
          aria-label="Filter provider keys by region"
        >
          <option value="all">All</option>
          {REGIONS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </div>

      <DataTable
        caption="Provider keys"
        columns={columns}
        rows={filteredKeys}
        getRowId={(k) => k.id}
        isLoading={keysQuery.isLoading}
        error={
          keysQuery.isError
            ? {
                title: "Unable to load provider keys",
                detail: keysQuery.error instanceof Error ? keysQuery.error.message : "Unknown error",
                onRetry: () => void keysQuery.refetch(),
              }
            : null
        }
        empty={
          keys.length === 0
            ? { title: "No provider keys", detail: "Add an API key to start routing traffic to LLM providers." }
            : { title: "No keys in this region", detail: "Choose another region or All." }
        }
      />

      <AddKeyModal
        open={showAdd}
        onClose={() => setShowAdd(false)}
        onSave={(data) => addMutation.mutate(data)}
        isSaving={addMutation.isPending}
      />
    </section>
  );
}
