import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, ToggleLeft, ToggleRight, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type {
  CreateModelRegistryRequest,
  DataClass,
  ModelRegistryEntry,
  ProviderKeyResponse,
  Rating,
  UpdateModelRegistryRequest,
} from "../../api/types";
import { Badge } from "../../components/ui/badge";
import { useConfirm } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../../components/ui/dialog";
import { PageHeader } from "../../components/ui/PageHeader";
import { useAuth } from "../../state/AuthContext";

const DATA_CLASSES: { value: DataClass; label: string }[] = [
  { value: "public", label: "Public" },
  { value: "internal", label: "Internal" },
  { value: "confidential", label: "Confidential" },
  { value: "secret", label: "Secret" },
];
const REGIONS = [
  { value: "us", label: "US" },
  { value: "eu", label: "EU" },
  { value: "ap", label: "Asia-Pacific" },
  { value: "global", label: "Global" },
];
const RATINGS: Rating[] = ["low", "medium", "high"];

const CLASS_LABEL = Object.fromEntries(DATA_CLASSES.map((c) => [c.value, c.label]));
const REGION_LABEL = Object.fromEntries(REGIONS.map((r) => [r.value, r.label]));
const RISK_VARIANT: Record<Rating, "success" | "warning" | "error"> = { low: "success", medium: "warning", high: "error" };

/** "provider/name" -> provider, the part a key has to serve. */
function providerOf(modelId: string): string {
  return modelId.split("/", 1)[0] ?? "";
}

function parseCapabilities(text: string): string[] {
  return text
    .split(",")
    .map((c) => c.trim().toUpperCase().replace(/\s+/g, "_"))
    .filter(Boolean);
}

interface FormState {
  modelId: string;
  keyId: string;
  maxDataClass: DataClass;
  regions: string[];
  risk: Rating;
  retention: string;
  trains: boolean;
  capabilities: string;
  owner: string;
  enabled: boolean;
}

function initialState(entry: ModelRegistryEntry | null): FormState {
  return {
    modelId: entry?.model_id ?? "",
    keyId: entry?.provider_key_id ?? "",
    maxDataClass: entry?.max_data_class ?? "internal",
    regions: entry?.regions ?? [],
    risk: entry?.risk_rating ?? "medium",
    retention: entry?.retention_days != null ? String(entry.retention_days) : "",
    trains: entry?.trains_on_data ?? false,
    capabilities: (entry?.capabilities ?? []).join(", "),
    owner: entry?.owner ?? "",
    enabled: entry?.enabled ?? true,
  };
}

function EntryDialog({
  entry,
  keys,
  onClose,
  onCreate,
  onUpdate,
  isSaving,
}: {
  entry: ModelRegistryEntry | null;
  keys: ProviderKeyResponse[];
  onClose: () => void;
  onCreate: (data: CreateModelRegistryRequest) => void;
  onUpdate: (id: string, data: UpdateModelRegistryRequest) => void;
  isSaving: boolean;
}) {
  const [form, setForm] = useState<FormState>(() => initialState(entry));
  const editing = entry !== null;
  const provider = providerOf(form.modelId);
  const matchingKeys = keys.filter((k) => k.provider === provider);

  function patch(change: Partial<FormState>) {
    setForm((f) => ({ ...f, ...change }));
  }

  function toggleRegion(region: string) {
    patch({ regions: form.regions.includes(region) ? form.regions.filter((r) => r !== region) : [...form.regions, region] });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!editing && !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.:@/-]+$/.test(form.modelId.trim())) {
      toast.error("Model must look like provider/name, for example openai/gpt-4o.");
      return;
    }
    if (form.regions.length === 0) {
      toast.error("Choose at least one region.");
      return;
    }
    const retention = form.retention.trim() === "" ? null : Number(form.retention);
    if (retention !== null && (!Number.isInteger(retention) || retention < 0)) {
      toast.error("Retention must be a whole number of days, or empty if unknown.");
      return;
    }
    const common = {
      provider_key_id: form.keyId || null,
      max_data_class: form.maxDataClass,
      regions: form.regions,
      risk_rating: form.risk,
      retention_days: retention,
      trains_on_data: form.trains,
      capabilities: parseCapabilities(form.capabilities),
      owner: form.owner.trim() || null,
      enabled: form.enabled,
    };
    if (editing) onUpdate(entry.id, common);
    else onCreate({ model_id: form.modelId.trim(), ...common });
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{editing ? `Edit ${entry.model_id}` : "Add model"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="stack-form">
          {editing ? null : (
            <label className="inline-control">
              Model
              <input type="text" value={form.modelId} onChange={(e) => patch({ modelId: e.target.value })} placeholder="openai/gpt-4o" autoComplete="off" required />
            </label>
          )}
          <label className="inline-control">
            Provider key
            <select value={form.keyId} onChange={(e) => patch({ keyId: e.target.value })}>
              <option value="">None (not routable)</option>
              {matchingKeys.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.key_alias}
                  {k.api_base ? ` (${k.api_base})` : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="inline-control">
            Most sensitive data this model is cleared for
            <select value={form.maxDataClass} onChange={(e) => patch({ maxDataClass: e.target.value as DataClass })}>
              {DATA_CLASSES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
          <fieldset className="inline-control">
            <legend>Regions where it processes data</legend>
            {REGIONS.map((r) => (
              <label key={r.value}>
                <input type="checkbox" checked={form.regions.includes(r.value)} onChange={() => toggleRegion(r.value)} /> {r.label}
              </label>
            ))}
          </fieldset>
          <label className="inline-control">
            Risk rating
            <select value={form.risk} onChange={(e) => patch({ risk: e.target.value as Rating })}>
              {RATINGS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>
          <label className="inline-control">
            Provider retention (days, empty if unknown)
            <input type="number" min="0" max="3650" value={form.retention} onChange={(e) => patch({ retention: e.target.value })} />
          </label>
          <label className="inline-control">
            Capabilities (comma separated)
            <input type="text" value={form.capabilities} onChange={(e) => patch({ capabilities: e.target.value })} placeholder="CODE_GENERATION, VISION" />
          </label>
          <label className="inline-control">
            Owner
            <input type="text" value={form.owner} onChange={(e) => patch({ owner: e.target.value })} placeholder="platform-team" />
          </label>
          <label className="inline-control">
            <span>
              <input type="checkbox" checked={form.trains} onChange={(e) => patch({ trains: e.target.checked })} /> The provider may train on our data
            </span>
          </label>
          <label className="inline-control">
            <span>
              <input type="checkbox" checked={form.enabled} onChange={(e) => patch({ enabled: e.target.checked })} /> Enabled
            </span>
          </label>
          <DialogFooter>
            <button type="button" onClick={onClose} className="btn-outline">
              Cancel
            </button>
            <button type="submit" disabled={isSaving} className="bg-accent-sky">
              {isSaving ? "Saving…" : editing ? "Save changes" : "Add model"}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ModelRegistryPage() {
  const { token } = useAuth();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [dialog, setDialog] = useState<{ entry: ModelRegistryEntry | null } | null>(null);

  const entriesQuery = useQuery({
    queryKey: ["model-registry", token],
    queryFn: () => apiClient.get<ModelRegistryEntry[]>("/api/v1/model-registry", token!),
    enabled: Boolean(token),
  });
  const keysQuery = useQuery({
    queryKey: ["provider-keys", token],
    queryFn: () => apiClient.get<ProviderKeyResponse[]>("/api/v1/provider-keys", token!),
    enabled: Boolean(token),
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["model-registry"] });
  const fail = (fallback: string) => (err: unknown) => toast.error(err instanceof Error ? err.message : fallback);

  const createMutation = useMutation({
    mutationFn: (data: CreateModelRegistryRequest) => apiClient.post<ModelRegistryEntry>("/api/v1/model-registry", data, token!),
    onSuccess: () => {
      toast.success("Model added.");
      void refresh();
      setDialog(null);
    },
    onError: fail("Failed to add model"),
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateModelRegistryRequest }) =>
      apiClient.patch<ModelRegistryEntry>(`/api/v1/model-registry/${id}`, data, token!),
    onSuccess: () => {
      toast.success("Model updated.");
      void refresh();
      setDialog(null);
    },
    onError: fail("Failed to update model"),
  });
  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.del(`/api/v1/model-registry/${id}`, token!),
    onSuccess: () => {
      toast.success("Model removed.");
      void refresh();
    },
    onError: fail("Failed to remove model"),
  });

  async function handleDelete(entry: ModelRegistryEntry) {
    const ok = await confirm({
      title: `Remove ${entry.model_id}?`,
      description: "The model stays available to clients until routing starts using the registry, then it will no longer be an authorized choice.",
      confirmLabel: "Remove model",
      destructive: true,
    });
    if (ok) deleteMutation.mutate(entry.id);
  }

  const entries = entriesQuery.data ?? [];
  const keys = keysQuery.data ?? [];
  const keyAlias = (id: string | null) => keys.find((k) => k.id === id)?.key_alias;

  const columns: Column<ModelRegistryEntry>[] = [
    { key: "model", header: "Model", mono: true, cell: (e) => e.model_id },
    {
      key: "key",
      header: "Provider key",
      cell: (e) =>
        e.provider_key_id ? (
          (keyAlias(e.provider_key_id) ?? "—")
        ) : (
          <Badge variant="warning" title="No key is attached, so this model cannot be routed">
            Not attached
          </Badge>
        ),
    },
    {
      key: "class",
      header: "Max data class",
      cell: (e) => (
        <Badge variant="muted" className="text-xs">
          {CLASS_LABEL[e.max_data_class] ?? e.max_data_class}
        </Badge>
      ),
    },
    { key: "regions", header: "Regions", cell: (e) => e.regions.map((r) => REGION_LABEL[r] ?? r).join(", ") },
    { key: "risk", header: "Risk", cell: (e) => <Badge variant={RISK_VARIANT[e.risk_rating]}>{e.risk_rating}</Badge> },
    {
      key: "retention",
      header: "Retention",
      align: "right",
      mono: true,
      cell: (e) => (e.retention_days != null ? `${e.retention_days} d` : "—"),
    },
    {
      key: "trains",
      header: "Trains on data",
      cell: (e) => (e.trains_on_data ? <Badge variant="warning">Yes</Badge> : <span className="text-muted text-xs">No</span>),
    },
    { key: "status", header: "Status", cell: (e) => <Badge variant={e.enabled ? "success" : "muted"}>{e.enabled ? "Enabled" : "Disabled"}</Badge> },
    {
      key: "actions",
      header: "Actions",
      cell: (e) => (
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn-icon-only"
            onClick={() => updateMutation.mutate({ id: e.id, data: { enabled: !e.enabled } })}
            aria-label={e.enabled ? `Disable ${e.model_id}` : `Enable ${e.model_id}`}
          >
            {e.enabled ? <ToggleRight size={18} className="text-accent-teal" aria-hidden /> : <ToggleLeft size={18} className="text-muted" aria-hidden />}
          </button>
          <button type="button" className="btn-icon-only" onClick={() => setDialog({ entry: e })} aria-label={`Edit ${e.model_id}`}>
            <Pencil size={14} aria-hidden />
          </button>
          <button type="button" className="btn-icon-only" onClick={() => void handleDelete(e)} aria-label={`Remove ${e.model_id}`}>
            <Trash2 size={14} className="text-accent-rose" aria-hidden />
          </button>
        </div>
      ),
    },
  ];

  return (
    <section className="page-wrap">
      <PageHeader
        title="Model registry"
        description="The models your organization has vetted: where each runs, how long the provider keeps data, and the most sensitive data it may receive."
        actions={
          <button type="button" onClick={() => setDialog({ entry: null })} className="flex items-center gap-1.5 bg-accent-sky" aria-label="Add model">
            <Plus size={15} aria-hidden />
            Add model
          </button>
        }
      />
      <DataTable
        caption="Model registry"
        columns={columns}
        rows={entries}
        getRowId={(e) => e.id}
        isLoading={entriesQuery.isLoading}
        error={
          entriesQuery.isError
            ? {
                title: "Unable to load the model registry",
                detail: entriesQuery.error instanceof Error ? entriesQuery.error.message : "Unknown error",
                onRetry: () => void entriesQuery.refetch(),
              }
            : null
        }
        empty={{ title: "No models yet", detail: "Add the models you have vetted. Routing will only choose from this list once it uses the registry." }}
      />
      {dialog ? (
        <EntryDialog
          key={dialog.entry?.id ?? "new"}
          entry={dialog.entry}
          keys={keys}
          onClose={() => setDialog(null)}
          onCreate={(data) => createMutation.mutate(data)}
          onUpdate={(id, data) => updateMutation.mutate({ id, data })}
          isSaving={createMutation.isPending || updateMutation.isPending}
        />
      ) : null}
    </section>
  );
}
