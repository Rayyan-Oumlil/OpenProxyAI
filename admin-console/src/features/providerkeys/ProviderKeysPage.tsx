import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, ToggleLeft, ToggleRight, Plug2 } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type {
  ProviderKeyResponse,
  CreateProviderKeyRequest,
  UpdateProviderKeyRequest,
} from "../../api/types";
import { LoadingState } from "../../components/LoadingState";
import { ErrorState } from "../../components/ErrorState";
import { EmptyState } from "../../components/EmptyState";
import { Badge } from "../../components/ui/badge";
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

  function handleDelete(id: string) {
    if (!window.confirm("Delete this provider key? This action cannot be undone.")) return;
    deleteMutation.mutate(id);
  }

  if (keysQuery.isLoading) return <LoadingState label="Loading provider keys…" />;
  if (keysQuery.isError)
    return (
      <ErrorState
        title="Unable to load provider keys"
        detail={keysQuery.error instanceof Error ? keysQuery.error.message : "Unknown error"}
      />
    );

  const keys = keysQuery.data ?? [];
  const filteredKeys =
    regionFilter === "all" ? keys : keys.filter((k) => k.region === regionFilter);

  return (
    <section className="page-wrap">
      <header className="page-header with-controls">
        <div>
          <p className="eyebrow">LLM Providers</p>
          <h1>Provider Keys</h1>
        </div>
        <button
          type="button"
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 bg-accent-sky"
          aria-label="Add provider key"
        >
          <Plus size={15} aria-hidden />
          Add Provider Key
        </button>
      </header>

      {keys.length === 0 ? (
        <EmptyState
          title="No provider keys"
          detail="Add an API key to start routing traffic to LLM providers."
        />
      ) : (
        <section className="surface-panel">
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
          <table className="data-table">
            <thead>
              <tr>
                <th>Provider</th>
                <th>Alias</th>
                <th>Region</th>
                <th>Key Prefix</th>
                <th>Weight</th>
                {(keys.some((k) => k.effective_weight != null) || keys.some((k) => k.latency_p99_ms != null)) && (
                  <>
                    <th title="Adaptive LB: p99 latency (ms)">P99 (ms)</th>
                    <th title="Adaptive LB: error rate">Error %</th>
                    <th title="Adaptive LB: effective weight used in selection">Eff. Weight</th>
                  </>
                )}
                <th>Circuit</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredKeys.map((k) => (
                <tr key={k.id}>
                  <td>
                    <div className="flex items-center gap-1.5">
                      <Plug2 size={13} className="text-muted" aria-hidden />
                      {k.provider}
                    </div>
                  </td>
                  <td>{k.key_alias ?? k.alias ?? "—"}</td>
                  <td>
                    <Badge variant="muted" className="text-xs">
                      {REGIONS.find((r) => r.value === k.region)?.label ?? k.region ?? "US"}
                    </Badge>
                  </td>
                  <td>
                    <code>{k.key_prefix}…</code>
                  </td>
                  <td>{k.weight}</td>
                  {(keys.some((x) => x.effective_weight != null) || keys.some((x) => x.latency_p99_ms != null)) && (
                    <>
                      <td className="text-muted text-sm">
                        {k.latency_p99_ms != null ? Math.round(k.latency_p99_ms) : "—"}
                      </td>
                      <td className="text-muted text-sm">
                        {k.error_rate != null ? `${(k.error_rate * 100).toFixed(1)}%` : "—"}
                      </td>
                      <td className="text-muted text-sm">
                        {k.effective_weight != null ? k.effective_weight : "—"}
                      </td>
                    </>
                  )}
                  <td>
                    {k.circuit_open_until != null && k.circuit_open_until > Date.now() / 1000 ? (
                      <Badge variant="warning" title={`Open until ${new Date(k.circuit_open_until * 1000).toLocaleString()}`}>
                        Open
                      </Badge>
                    ) : (
                      <span className="text-muted text-xs">Closed</span>
                    )}
                  </td>
                  <td>
                    <Badge variant={k.is_active ? "success" : "muted"}>
                      {k.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </td>
                  <td className="text-muted text-sm">
                    {formatDate(k.created_at)}
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => toggleMutation.mutate({ id: k.id, is_active: !k.is_active })}
                        className="btn-icon-only"
                        aria-label={k.is_active ? `Deactivate ${k.key_alias ?? k.provider}` : `Activate ${k.key_alias ?? k.provider}`}
                      >
                        {k.is_active ? (
                          <ToggleRight size={18} className="text-accent-teal" aria-hidden />
                        ) : (
                          <ToggleLeft size={18} className="text-muted" aria-hidden />
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(k.id)}
                        className="btn-icon-only"
                        aria-label={`Delete ${k.key_alias ?? k.provider}`}
                      >
                        <Trash2 size={14} className="text-accent-rose" aria-hidden />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <AddKeyModal
        open={showAdd}
        onClose={() => setShowAdd(false)}
        onSave={(data) => addMutation.mutate(data)}
        isSaving={addMutation.isPending}
      />
    </section>
  );
}
