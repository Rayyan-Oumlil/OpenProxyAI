import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Play, Square, BarChart3, X } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type {
  ExperimentResponse,
  CreateExperimentRequest,
  UpdateExperimentRequest,
  VariantMetrics,
} from "../../api/types";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { formatDate } from "../../lib/utils";
import { Badge } from "../../components/ui/badge";
import { useConfirm } from "../../components/ui/ConfirmDialog";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "../../components/ui/dialog";
import { useAuth } from "../../state/AuthContext";
import { chanceLabel, DELTA_CHOICES, isAdaptive, ratingsStillNeeded, resultKey, samplesByModel, variantsChanged, winnerOf } from "./adaptive";

type VariantDraft = { model: string; traffic_weight: number };

function ExperimentModal({
  open,
  onClose,
  onSave,
  isSaving,
  initial,
}: {
  open: boolean;
  onClose: () => void;
  onSave: (data: CreateExperimentRequest | UpdateExperimentRequest) => void;
  isSaving: boolean;
  initial?: ExperimentResponse | null;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [targetModel, setTargetModel] = useState(initial?.target_model ?? "");
  const initialVariants: VariantDraft[] = initial?.variants?.map((v) => ({ model: v.model, traffic_weight: v.traffic_weight })) ?? [{ model: "", traffic_weight: 50 }];
  const [variants, setVariants] = useState<VariantDraft[]>(initialVariants);
  const [adaptive, setAdaptive] = useState(initial ? isAdaptive(initial) : false);
  const [metric, setMetric] = useState(initial?.metric ?? "thumbs");
  const [minSamples, setMinSamples] = useState(String(initial?.min_samples_per_variant ?? 30));
  const [delta, setDelta] = useState(String(initial?.delta ?? 0.01));
  const [floor, setFloor] = useState(String(initial?.weight_floor ?? 5));

  function addVariant() {
    setVariants([...variants, { model: "", traffic_weight: 50 }]);
  }

  function removeVariant(idx: number) {
    setVariants(variants.filter((_, i) => i !== idx));
  }

  function updateVariant(idx: number, field: "model" | "traffic_weight", value: string | number) {
    const next = [...variants];
    if (field === "model") next[idx] = { ...next[idx], model: String(value) };
    else next[idx] = { ...next[idx], traffic_weight: Number(value) };
    setVariants(next);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const valid = variants.filter((v) => v.model.trim());
    if (!name.trim()) {
      toast.error("Name is required.");
      return;
    }
    if (!targetModel.trim()) {
      toast.error("Target model is required.");
      return;
    }
    if (valid.length === 0) {
      toast.error("At least one variant with a model is required.");
      return;
    }
    if (adaptive) {
      if (valid.length < 2) {
        toast.error("An adaptive experiment compares variants, so it needs at least two.");
        return;
      }
      if (!/^[A-Za-z0-9_.:-]{1,100}$/.test(metric.trim())) {
        toast.error("The metric is the name of a feedback score, for example thumbs.");
        return;
      }
      if (!(Number(minSamples) >= 20)) {
        toast.error("Each variant needs at least 20 ratings before anything is decided.");
        return;
      }
    }
    const settings = adaptive
      ? { mode: "adaptive" as const, metric: metric.trim(), min_samples_per_variant: Math.round(Number(minSamples)), delta: Number(delta), weight_floor: Math.round(Number(floor)) || 5 }
      : { mode: "static" as const };
    if (initial) {
      // Replacing the variants also detaches the ratings collected so far, so send them only when they changed.
      const changed = variantsChanged(initialVariants, valid);
      onSave({ name: name.trim(), ...settings, ...(changed ? { variants: valid } : {}) });
    } else {
      onSave({ name: name.trim(), target_model: targetModel.trim(), variants: valid, ...(adaptive ? settings : {}) });
    }
    onClose();
  }

  const changedVariants = initial ? variantsChanged(initialVariants, variants.filter((v) => v.model.trim())) : false;

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{initial ? "Edit Experiment" : "Create Experiment"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="stack-form">
          <label className="inline-control">
            Name
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. GPT-4o vs Claude A/B"
            />
          </label>
          <label className="inline-control">
            Target model (requested model that triggers experiment)
            <input
              type="text"
              value={targetModel}
              onChange={(e) => setTargetModel(e.target.value)}
              placeholder="e.g. openai/gpt-4o"
              disabled={Boolean(initial)}
            />
          </label>
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">Variants</span>
              <button
                type="button"
                onClick={addVariant}
                className="flex items-center gap-1 text-accent-sky text-xs"
              >
                <Plus size={12} aria-hidden />
                Add variant
              </button>
            </div>
            <div className="flex flex-col gap-2">
              {variants.map((v, idx) => (
                <div key={idx} className="flex items-center gap-2 variant-row">
                  <label className="sr-only" htmlFor={`variant-model-${idx}`}>
                    Variant {idx + 1} model
                  </label>
                  <input
                    id={`variant-model-${idx}`}
                    type="text"
                    value={v.model}
                    onChange={(e) => updateVariant(idx, "model", e.target.value)}
                    placeholder="e.g. anthropic/claude-3-5-sonnet"
                    className="variant-input"
                    aria-label={`Variant ${idx + 1} model`}
                  />
                  <label className="sr-only" htmlFor={`variant-weight-${idx}`}>
                    Variant {idx + 1} traffic weight
                  </label>
                  <input
                    id={`variant-weight-${idx}`}
                    type="number"
                    value={v.traffic_weight}
                    onChange={(e) => updateVariant(idx, "traffic_weight", e.target.value)}
                    min={1}
                    max={100}
                    className="variant-weight-input"
                    aria-label={`Variant ${idx + 1} traffic weight`}
                  />
                  <span className="text-muted-xs">weight</span>
                  {variants.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeVariant(idx)}
                      className="btn-icon-only"
                      aria-label={`Remove variant ${idx + 1}`}
                    >
                      <X size={14} className="text-accent-rose" aria-hidden />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          <fieldset className="stack-form">
            <legend className="text-sm font-medium">Traffic split</legend>
            <label className="flex items-start gap-2 text-sm">
              <input type="radio" name="split-mode" checked={!adaptive} onChange={() => setAdaptive(false)} />
              <span>
                <strong>Fixed.</strong> The weights above stay as you set them.
              </span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input type="radio" name="split-mode" checked={adaptive} onChange={() => setAdaptive(true)} />
              <span>
                <strong>Adaptive.</strong> Traffic moves toward the variant people rate higher, and the test stops by itself when one is clearly better. The winner is recorded, never switched on for you.
              </span>
            </label>
            {adaptive ? (
              <>
                <label className="inline-control">
                  Feedback score to judge by (values from 0 to 1, such as thumbs)
                  <input value={metric} onChange={(e) => setMetric(e.target.value)} />
                </label>
                <div className="flex gap-3">
                  <label className="inline-control">
                    Ratings needed per variant (20 or more)
                    <input type="number" min={20} value={minSamples} onChange={(e) => setMinSamples(e.target.value)} />
                  </label>
                  <label className="inline-control">
                    Lowest share of traffic (%)
                    <input type="number" min={1} max={20} value={floor} onChange={(e) => setFloor(e.target.value)} />
                  </label>
                </div>
                <label className="inline-control">
                  How sure before it stops
                  <select value={delta} onChange={(e) => setDelta(e.target.value)}>
                    {DELTA_CHOICES.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </label>
                <p className="text-muted text-sm">{DELTA_CHOICES.find((c) => String(c.value) === delta)?.detail}</p>
                {initial && changedVariants ? (
                  <p role="note" className="text-sm">
                    Changing the variants replaces them, so ratings collected so far no longer count and any recorded winner is cleared.
                  </p>
                ) : null}
              </>
            ) : null}
          </fieldset>

          <DialogFooter>
            <button type="button" onClick={onClose} className="btn-outline">
              Cancel
            </button>
            <button type="submit" disabled={isSaving} className="bg-accent-sky">
              {isSaving ? "Saving…" : initial ? "Update" : "Create"}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function AdaptiveSummary({ experiment, results }: { experiment: ExperimentResponse; results: NonNullable<ReturnType<typeof useResults>["data"]> }) {
  const adaptive = results.adaptive;
  if (!adaptive) return null;
  const winner = winnerOf(experiment);
  const needed = ratingsStillNeeded(adaptive);
  return (
    <div className="stack-form" role="status">
      {adaptive.error ? <p className="text-accent-rose text-sm">Not updating: {adaptive.error}</p> : null}
      {winner ? (
        <p className="text-sm">
          <Badge variant="success">Winner</Badge> <strong>{winner.model}</strong> came out ahead. This is recorded, not deployed: requests still go to <code>{experiment.target_model}</code> until you switch.
        </p>
      ) : adaptive.ready ? (
        <p className="text-sm">Every variant has enough ratings. No variant is clearly ahead yet, so the test keeps running.</p>
      ) : (
        <p className="text-sm">
          Collecting ratings: {samplesByModel(experiment, adaptive).map((s) => `${s.model} ${s.n}`).join(", ")} of {adaptive.min_samples_per_variant} each. Nothing moves until every variant has enough ({needed} more for the slowest).
        </p>
      )}
    </div>
  );
}

function useResults(experimentId: string, token: string, enabled: boolean) {
  return useQuery({
    queryKey: ["experiment-results", experimentId, token],
    queryFn: () => apiClient.getExperimentResults(experimentId, token),
    enabled: enabled && Boolean(token),
  });
}

function ResultsPanel({ experiment, token }: { experiment: ExperimentResponse; token: string }) {
  const resultsQuery = useResults(experiment.id, token, true);
  const adaptive = isAdaptive(experiment);

  return (
    <div className="results-panel" style={{ padding: "8px 4px" }}>
      {resultsQuery.isLoading && <p className="text-muted">Loading results…</p>}
      {resultsQuery.isError && (
        <p className="text-accent-rose">
          {resultsQuery.error instanceof Error ? resultsQuery.error.message : "Failed to load"}
        </p>
      )}
      {resultsQuery.data && <AdaptiveSummary experiment={experiment} results={resultsQuery.data} />}
      {resultsQuery.data && (
        <table className="data-table text-sm">
          <thead>
            <tr>
              <th>Model</th>
              {adaptive ? <th>Traffic</th> : null}
              {adaptive ? <th>Chance best</th> : null}
              <th>Requests</th>
              <th>Avg latency (ms)</th>
              <th>Cost (USD)</th>
              <th>Quality</th>
              <th>Policy violations</th>
            </tr>
          </thead>
          <tbody>
            {resultsQuery.data.variants.length === 0 ? (
              <tr>
                <td colSpan={adaptive ? 8 : 6} className="text-muted">
                  No traffic yet
                </td>
              </tr>
            ) : (
              resultsQuery.data.variants.map((v: VariantMetrics, index: number) => (
                <tr key={resultKey(v, index)}>
                  <td>
                    <code>{v.model}</code>
                  </td>
                  {adaptive ? <td>{v.traffic_weight != null ? `${v.traffic_weight}%` : "—"}</td> : null}
                  {adaptive ? <td>{chanceLabel(v.probability_best)}</td> : null}
                  <td>{v.request_count}</td>
                  <td>{v.avg_latency_ms != null ? v.avg_latency_ms.toFixed(0) : "—"}</td>
                  <td>{Number(v.total_cost_usd).toFixed(4)}</td>
                  <td>
                    {v.scores && v.scores.length > 0 ? (
                      <span title={v.scores.map((s) => `${s.name}: ${s.avg.toFixed(2)} (n=${s.count})`).join(", ")}>
                        {v.scores.map((s) => `${s.name}: ${s.avg.toFixed(2)}`).join(", ")}
                      </span>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td>{v.policy_violations}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function ExperimentsPage() {
  const { token } = useAuth();
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<ExperimentResponse | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  const experimentsQuery = useQuery({
    queryKey: ["experiments", token],
    queryFn: () => apiClient.getExperiments(token!),
    enabled: Boolean(token),
  });

  const createMutation = useMutation({
    mutationFn: (data: CreateExperimentRequest) =>
      apiClient.createExperiment(data, token!),
    onSuccess: () => {
      toast.success("Experiment created.");
      qc.invalidateQueries({ queryKey: ["experiments", token] });
      setShowCreate(false);
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to create"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateExperimentRequest }) =>
      apiClient.updateExperiment(id, data, token!),
    onSuccess: () => {
      toast.success("Experiment updated.");
      qc.invalidateQueries({ queryKey: ["experiments", token] });
      setEditing(null);
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to update"),
  });

  const startMutation = useMutation({
    mutationFn: (id: string) => apiClient.startExperiment(id, token!),
    onSuccess: () => {
      toast.success("Experiment started.");
      qc.invalidateQueries({ queryKey: ["experiments", token] });
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to start"),
  });

  const stopMutation = useMutation({
    mutationFn: (id: string) => apiClient.stopExperiment(id, token!),
    onSuccess: () => {
      toast.success("Experiment stopped.");
      qc.invalidateQueries({ queryKey: ["experiments", token] });
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to stop"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.deleteExperiment(id, token!),
    onSuccess: () => {
      toast.success("Experiment deleted.");
      qc.invalidateQueries({ queryKey: ["experiments", token] });
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to delete"),
  });

  const confirm = useConfirm();

  async function handleDelete(id: string) {
    const ok = await confirm({
      title: "Delete experiment?",
      description: "This action cannot be undone.",
      confirmLabel: "Delete experiment",
      destructive: true,
    });
    if (!ok) return;
    deleteMutation.mutate(id);
  }

  async function handleStart(e: ExperimentResponse) {
    // Starting again clears a recorded winner; say so rather than do it silently.
    if (e.winner_variant_id) {
      const ok = await confirm({
        title: "Start this experiment again?",
        description: "It will clear the recorded winner and begin testing again.",
        confirmLabel: "Start again",
      });
      if (!ok) return;
    }
    startMutation.mutate(e.id);
  }

  const columns: Column<ExperimentResponse>[] = [
    {
      key: "name",
      header: "Name",
      cell: (e) => (
        <span className="flex items-center gap-1.5">
          <BarChart3 size={13} className="text-muted" aria-hidden />
          {e.name}
        </span>
      ),
    },
    { key: "target", header: "Target model", mono: true, cell: (e) => e.target_model },
    { key: "variants", header: "Variants", cell: (e) => <span className="text-sm">{e.variants.map((v) => `${v.model} (${v.traffic_weight})`).join(", ")}</span> },
    {
      key: "status",
      header: "Status",
      cell: (e) => {
        const winner = winnerOf(e);
        return (
          <span className="flex flex-wrap items-center gap-1">
            <Badge variant={e.is_active ? "success" : "muted"}>{e.is_active ? "Active" : "Inactive"}</Badge>
            {isAdaptive(e) ? <Badge variant="policy">Adaptive</Badge> : null}
            {winner ? <Badge variant="success">Winner: {winner.model}</Badge> : null}
            {e.adaptive_error ? <Badge variant="warning">Needs attention</Badge> : null}
          </span>
        );
      },
    },
    { key: "created", header: "Created", nowrap: true, cell: (e) => formatDate(e.created_at) },
    {
      key: "actions",
      header: "Actions",
      cell: (e) => (
        // A click on a control here must not also toggle the row's results.
        <div className="flex items-center gap-2" onClick={(event) => event.stopPropagation()}>
          {e.is_active ? (
            <button type="button" onClick={() => stopMutation.mutate(e.id)} className="btn-icon-only" aria-label={`Stop experiment ${e.name}`}>
              <Square size={14} className="text-accent-amber" aria-hidden />
            </button>
          ) : (
            <button type="button" onClick={() => void handleStart(e)} className="btn-icon-only" aria-label={`Start experiment ${e.name}`}>
              <Play size={14} className="text-accent-teal" aria-hidden />
            </button>
          )}
          <button type="button" onClick={() => setEditing(e)} className="btn-outline" aria-label={`Edit experiment ${e.name}`}>
            Edit
          </button>
          <button type="button" onClick={() => void handleDelete(e.id)} className="btn-icon-only" aria-label={`Delete experiment ${e.name}`}>
            <Trash2 size={14} className="text-accent-rose" aria-hidden />
          </button>
        </div>
      ),
    },
  ];

  return (
    <section className="page-wrap">
      <PageHeader
        title="Experiments"
        description="A/B test models by splitting traffic, then compare cost, latency and quality. An adaptive split follows the feedback your application sends."
        actions={
          <button type="button" onClick={() => setShowCreate(true)} className="flex items-center gap-1.5 bg-accent-sky" aria-label="Create new experiment">
            <Plus size={15} aria-hidden />
            New Experiment
          </button>
        }
      />

      <DataTable
        caption="Experiments"
        columns={columns}
        rows={experimentsQuery.data}
        getRowId={(e) => e.id}
        isLoading={experimentsQuery.isLoading}
        error={
          experimentsQuery.isError
            ? {
                title: "Unable to load experiments",
                detail: experimentsQuery.error instanceof Error ? experimentsQuery.error.message : "Unknown error",
                onRetry: () => void experimentsQuery.refetch(),
              }
            : null
        }
        empty={{ title: "No experiments", detail: "Create an experiment to A/B test different models with traffic splitting." }}
        onRowClick={(e) => setOpenId(openId === e.id ? null : e.id)}
        getRowLabel={(e) => `${e.name} results`}
        expandedId={openId}
        renderExpanded={(e) => (token ? <ResultsPanel experiment={e} token={token} /> : null)}
      />

      <ExperimentModal
        key="create"
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSave={(data) => createMutation.mutate(data as CreateExperimentRequest)}
        isSaving={createMutation.isPending}
      />

      <ExperimentModal
        key={editing?.id ?? "edit"}
        open={editing != null}
        onClose={() => setEditing(null)}
        onSave={(data) => editing && updateMutation.mutate({ id: editing.id, data })}
        isSaving={updateMutation.isPending}
        initial={editing ?? undefined}
      />
    </section>
  );
}
