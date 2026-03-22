import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Play, Square, BarChart3, ChevronDown, ChevronRight, X } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type {
  ExperimentResponse,
  CreateExperimentRequest,
  UpdateExperimentRequest,
  VariantMetrics,
} from "../../api/types";
import { LoadingState } from "../../components/LoadingState";
import { ErrorState } from "../../components/ErrorState";
import { EmptyState } from "../../components/EmptyState";
import { Badge } from "../../components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "../../components/ui/dialog";
import { useAuth } from "../../state/AuthContext";

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
  const [variants, setVariants] = useState<Array<{ model: string; traffic_weight: number }>>(
    initial?.variants?.map((v) => ({ model: v.model, traffic_weight: v.traffic_weight })) ?? [
      { model: "", traffic_weight: 50 },
    ]
  );

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
    if (initial) {
      onSave({ name: name.trim(), target_model: targetModel.trim(), variants: valid });
    } else {
      onSave({ name: name.trim(), target_model: targetModel.trim(), variants: valid });
    }
    onClose();
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
            />
          </label>
          <div>
            <div className="flex items-center justify-between" style={{ marginBottom: "0.5rem" }}>
              <span style={{ fontSize: "0.875rem", fontWeight: 500 }}>Variants</span>
              <button
                type="button"
                onClick={addVariant}
                className="flex items-center gap-1"
                style={{ fontSize: "0.8rem", color: "var(--accent-sky)" }}
              >
                <Plus size={12} />
                Add variant
              </button>
            </div>
            <div className="flex flex-col gap-2">
              {variants.map((v, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2"
                  style={{
                    padding: "0.5rem",
                    border: "1px solid var(--line)",
                    borderRadius: "8px",
                    background: "var(--surface)",
                  }}
                >
                  <input
                    type="text"
                    value={v.model}
                    onChange={(e) => updateVariant(idx, "model", e.target.value)}
                    placeholder="e.g. anthropic/claude-3-5-sonnet"
                    style={{ flex: 1, padding: "0.35rem 0.5rem" }}
                  />
                  <input
                    type="number"
                    value={v.traffic_weight}
                    onChange={(e) => updateVariant(idx, "traffic_weight", e.target.value)}
                    min={1}
                    max={100}
                    style={{ width: 70, padding: "0.35rem 0.5rem" }}
                  />
                  <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>weight</span>
                  {variants.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeVariant(idx)}
                      style={{ border: "none", background: "transparent", padding: "2px", cursor: "pointer" }}
                    >
                      <X size={14} style={{ color: "var(--accent-rose)" }} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
          <DialogFooter>
            <button
              type="button"
              onClick={onClose}
              style={{ background: "transparent", color: "var(--muted)", border: "1px solid var(--line)" }}
            >
              Cancel
            </button>
            <button type="submit" disabled={isSaving} style={{ background: "var(--accent-sky)" }}>
              {isSaving ? "Saving…" : initial ? "Update" : "Create"}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ResultsPanel({ experimentId, token }: { experimentId: string; token: string }) {
  const [open, setOpen] = useState(false);
  const resultsQuery = useQuery({
    queryKey: ["experiment-results", experimentId, token],
    queryFn: () => apiClient.getExperimentResults(experimentId, token),
    enabled: open && Boolean(token),
  });

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1"
        style={{ fontSize: "0.8rem", color: "var(--accent-sky)", border: "none", background: "transparent", cursor: "pointer" }}
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        View results
      </button>
      {open && (
        <div
          style={{
            marginTop: "0.75rem",
            padding: "1rem",
            border: "1px solid var(--line)",
            borderRadius: "8px",
            background: "var(--surface)",
          }}
        >
          {resultsQuery.isLoading && <p style={{ color: "var(--muted)" }}>Loading results…</p>}
          {resultsQuery.isError && (
            <p style={{ color: "var(--accent-rose)" }}>
              {resultsQuery.error instanceof Error ? resultsQuery.error.message : "Failed to load"}
            </p>
          )}
          {resultsQuery.data && (
            <table className="data-table" style={{ fontSize: "0.85rem" }}>
              <thead>
                <tr>
                  <th>Model</th>
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
                    <td colSpan={6} style={{ color: "var(--muted)" }}>
                      No traffic yet
                    </td>
                  </tr>
                ) : (
                  resultsQuery.data.variants.map((v: VariantMetrics) => (
                    <tr key={v.model}>
                      <td>
                        <code>{v.model}</code>
                      </td>
                      <td>{v.request_count}</td>
                      <td>{v.avg_latency_ms != null ? v.avg_latency_ms.toFixed(0) : "—"}</td>
                      <td>{Number(v.total_cost_usd).toFixed(4)}</td>
                      <td>
                        {v.scores && v.scores.length > 0 ? (
                          <span title={v.scores.map((s) => `${s.name}: ${s.avg.toFixed(2)} (n=${s.count})`).join(", ")}>
                            {v.scores.map((s) => `${s.name}: ${s.avg.toFixed(2)}`).join(", ")}
                          </span>
                        ) : (
                          <span style={{ color: "var(--muted)" }}>—</span>
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
      )}
    </div>
  );
}

export function ExperimentsPage() {
  const { token } = useAuth();
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<ExperimentResponse | null>(null);

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
      qc.invalidateQueries({ queryKey: ["experiments"] });
      setShowCreate(false);
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to create"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateExperimentRequest }) =>
      apiClient.updateExperiment(id, data, token!),
    onSuccess: () => {
      toast.success("Experiment updated.");
      qc.invalidateQueries({ queryKey: ["experiments"] });
      setEditing(null);
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to update"),
  });

  const startMutation = useMutation({
    mutationFn: (id: string) => apiClient.startExperiment(id, token!),
    onSuccess: () => {
      toast.success("Experiment started.");
      qc.invalidateQueries({ queryKey: ["experiments"] });
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to start"),
  });

  const stopMutation = useMutation({
    mutationFn: (id: string) => apiClient.stopExperiment(id, token!),
    onSuccess: () => {
      toast.success("Experiment stopped.");
      qc.invalidateQueries({ queryKey: ["experiments"] });
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to stop"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.deleteExperiment(id, token!),
    onSuccess: () => {
      toast.success("Experiment deleted.");
      qc.invalidateQueries({ queryKey: ["experiments"] });
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to delete"),
  });

  function handleDelete(id: string) {
    if (!window.confirm("Delete this experiment? This action cannot be undone.")) return;
    deleteMutation.mutate(id);
  }

  if (experimentsQuery.isLoading) return <LoadingState label="Loading experiments…" />;
  if (experimentsQuery.isError)
    return (
      <ErrorState
        title="Unable to load experiments"
        detail={experimentsQuery.error instanceof Error ? experimentsQuery.error.message : "Unknown error"}
      />
    );

  const experiments = experimentsQuery.data ?? [];

  return (
    <section className="page-wrap">
      <header className="page-header with-controls">
        <div>
          <p className="eyebrow">A/B Testing</p>
          <h1>Experiments</h1>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5"
          style={{ background: "var(--accent-sky)" }}
        >
          <Plus size={15} />
          New Experiment
        </button>
      </header>

      {experiments.length === 0 ? (
        <EmptyState
          title="No experiments"
          detail="Create an experiment to A/B test different models with traffic splitting."
        />
      ) : (
        <section className="surface-panel">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Target model</th>
                <th>Variants</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((e) => (
                <tr key={e.id}>
                  <td>
                    <div className="flex items-center gap-1.5">
                      <BarChart3 size={13} style={{ color: "var(--muted)" }} />
                      {e.name}
                    </div>
                  </td>
                  <td>
                    <code>{e.target_model}</code>
                  </td>
                  <td>
                    <span style={{ fontSize: "0.85rem" }}>
                      {e.variants.map((v) => `${v.model} (${v.traffic_weight})`).join(", ")}
                    </span>
                  </td>
                  <td>
                    <Badge variant={e.is_active ? "success" : "muted"}>
                      {e.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </td>
                  <td style={{ color: "var(--muted)", fontSize: "0.82rem" }}>
                    {new Date(e.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-2">
                        {e.is_active ? (
                          <button
                            type="button"
                            title="Stop"
                            onClick={() => stopMutation.mutate(e.id)}
                            style={{ border: "none", background: "transparent", padding: "2px", cursor: "pointer" }}
                          >
                            <Square size={14} style={{ color: "var(--accent-amber)" }} />
                          </button>
                        ) : (
                          <button
                            type="button"
                            title="Start"
                            onClick={() => startMutation.mutate(e.id)}
                            style={{ border: "none", background: "transparent", padding: "2px", cursor: "pointer" }}
                          >
                            <Play size={14} style={{ color: "var(--accent-teal)" }} />
                          </button>
                        )}
                        <button
                          type="button"
                          title="Edit"
                          onClick={() => setEditing(e)}
                          style={{ fontSize: "0.75rem", color: "var(--accent-sky)" }}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          title="Delete"
                          onClick={() => handleDelete(e.id)}
                          style={{ border: "none", background: "transparent", padding: "2px", cursor: "pointer" }}
                        >
                          <Trash2 size={14} style={{ color: "var(--accent-rose)" }} />
                        </button>
                      </div>
                      {token && <ResultsPanel experimentId={e.id} token={token} />}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

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
