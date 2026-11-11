import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Square } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import { isRunActive, type CreateEvalRunRequest, type Dataset, type EvalRun, type EvalRunItem, type Evaluator } from "../../api/evaluationTypes";
import { Badge } from "../../components/ui/badge";
import { Fact } from "../../components/ui/Fact";
import { useConfirm } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../../components/ui/dialog";
import { PageHeader } from "../../components/ui/PageHeader";
import { durationSeconds, money, percent, previewOf, STATUS_LABEL, STATUS_VARIANT } from "../../lib/evaluation";
import { formatDate } from "../../lib/utils";
import { useAuth } from "../../state/AuthContext";

const RUNS = "/api/v1/eval-runs";
const PAGE_SIZE = 50;
const POLL_MS = 3000;

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export function RunBadge({ status }: { status: EvalRun["status"] }) {
  return <Badge variant={STATUS_VARIANT[status]}>{STATUS_LABEL[status]}</Badge>;
}

function NewRunDialog({ onClose, initialTemplateId }: { onClose: () => void; initialTemplateId?: string }) {
  const { token } = useAuth();
  const qc = useQueryClient();
  const datasets = useQuery({ queryKey: ["datasets", token], queryFn: () => apiClient.get<Dataset[]>("/api/v1/datasets", token!), enabled: Boolean(token) });
  const evaluators = useQuery({ queryKey: ["evaluators", token], queryFn: () => apiClient.get<Evaluator[]>("/api/v1/evaluators", token!), enabled: Boolean(token) });
  const templates = useQuery({ queryKey: ["prompt-templates", token], queryFn: () => apiClient.getPromptTemplates(token!), enabled: Boolean(token) });

  const [datasetId, setDatasetId] = useState("");
  const [evaluatorId, setEvaluatorId] = useState("");
  const [model, setModel] = useState("");
  const [templateId, setTemplateId] = useState(initialTemplateId ?? "");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [maxItems, setMaxItems] = useState("100");
  const [maxCost, setMaxCost] = useState("1");

  const start = useMutation({
    mutationFn: (body: CreateEvalRunRequest) => apiClient.post<EvalRun>(RUNS, body, token!),
    onSuccess: () => {
      toast.success("Run started.");
      void qc.invalidateQueries({ queryKey: ["eval-runs"] });
      onClose();
    },
    onError: (error) => toast.error(errorMessage(error, "Could not start the run")),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!datasetId) return toast.error("Choose a dataset.");
    if (!evaluatorId) return toast.error("Choose an evaluator.");
    if (!/^[^/\s]+\/\S+$/.test(model.trim())) return toast.error("The model must look like provider/name, for example openai/gpt-4o-mini.");
    start.mutate({
      dataset_id: datasetId,
      evaluator_id: evaluatorId,
      candidate_model: model.trim(),
      max_items: Number(maxItems) || 100,
      max_cost_usd: Number(maxCost) || 1,
      ...(templateId ? { prompt_template_id: templateId } : {}),
      ...(systemPrompt.trim() ? { system_prompt: systemPrompt } : {}),
    });
  }

  return (
    <Dialog open onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Start an eval run</DialogTitle>
          <DialogDescription>Sends each dataset item to the model, then scores the answers. It spends real money, so it stops at the cost cap.</DialogDescription>
        </DialogHeader>
        <form className="stack-form" onSubmit={submit}>
          <label className="inline-control">
            Dataset
            <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
              <option value="">Choose…</option>
              {(datasets.data ?? []).map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.item_count} items)
                </option>
              ))}
            </select>
          </label>
          <label className="inline-control">
            Evaluator
            <select value={evaluatorId} onChange={(e) => setEvaluatorId(e.target.value)}>
              <option value="">Choose…</option>
              {(evaluators.data ?? []).map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </label>
          <label className="inline-control">
            Model to test
            <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="openai/gpt-4o-mini" />
          </label>
          <label className="inline-control">
            Prompt template (optional)
            <select value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
              <option value="">None</option>
              {(templates.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} v{t.version}
                  {t.status === "draft" ? " (draft)" : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="inline-control">
            System prompt (optional; a run of a template uses the template’s own unless you write one here)
            <textarea className="textarea-short" value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} rows={2} />
          </label>
          <div className="flex gap-3">
            <label className="inline-control">
              Most items (1 to 500)
              <input type="number" min={1} max={500} value={maxItems} onChange={(e) => setMaxItems(e.target.value)} />
            </label>
            <label className="inline-control">
              Cost cap in USD (0.01 to 50)
              <input type="number" min={0.01} max={50} step="any" value={maxCost} onChange={(e) => setMaxCost(e.target.value)} />
            </label>
          </div>
          <DialogFooter>
            <button type="button" className="btn-outline" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" disabled={start.isPending} className="bg-accent-sky">
              Start run
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RunDetail({ run }: { run: EvalRun }) {
  const { token } = useAuth();
  const [outcome, setOutcome] = useState<"" | "passed" | "failed" | "error">("");
  const [offset, setOffset] = useState(0);

  const items = useQuery({
    queryKey: ["eval-run-items", run.id, outcome, offset],
    queryFn: () => apiClient.get<EvalRunItem[]>(`${RUNS}/${run.id}/items?limit=${PAGE_SIZE}&offset=${offset}${outcome ? `&outcome=${outcome}` : ""}`, token!),
    enabled: Boolean(token),
    refetchInterval: isRunActive(run.status) ? POLL_MS : false,
  });

  const columns: Column<EvalRunItem>[] = [
    {
      key: "result",
      header: "Result",
      cell: (i) => (i.error ? <Badge variant="warning">Not scored</Badge> : <Badge variant={i.passed ? "success" : "error"}>{i.passed ? "Passed" : "Failed"}</Badge>),
    },
    { key: "answer", header: "Answer", cell: (i) => (i.output ? <span className="text-sm">{previewOf([{ role: "user", content: i.output }], 120)}</span> : <span className="text-muted">—</span>) },
    { key: "why", header: "Why", cell: (i) => <span className="text-sm">{i.error ?? i.reason ?? "—"}</span> },
    { key: "score", header: "Score", align: "right", mono: true, cell: (i) => (i.score == null ? "—" : i.score.toFixed(2)) },
    { key: "cost", header: "Cost", align: "right", mono: true, cell: (i) => money(i.cost_usd) },
  ];

  const seconds = durationSeconds(run.started_at, run.finished_at);
  return (
    <div className="stack-form" style={{ padding: "12px 4px" }}>
      <dl className="trace-facts">
        <Fact label="Evaluator">{run.evaluator.name}</Fact>
        <Fact label="Scored">
          {run.scored_items} of {run.total_items}
        </Fact>
        <Fact label="Could not be scored">{run.failed_items}</Fact>
        <Fact label="Mean score">{run.mean_score == null ? "—" : run.mean_score.toFixed(2)}</Fact>
        <Fact label="Duration">{seconds == null ? "—" : `${seconds}s`}</Fact>
      </dl>
      {run.failed_items > 0 ? (
        <p className="text-sm" role="note">
          {run.failed_items} item{run.failed_items === 1 ? "" : "s"} could not be scored (refused by policy, a provider error, or no expected answer). They are left out of the pass rate rather than counted as failures.
        </p>
      ) : null}
      {run.error ? <p className="text-accent-rose text-sm">{run.error}</p> : null}
      <label className="inline-control" style={{ maxWidth: 240 }}>
        Show
        <select
          value={outcome}
          onChange={(e) => {
            setOutcome(e.target.value as typeof outcome);
            setOffset(0);
          }}
        >
          <option value="">All items</option>
          <option value="passed">Passed</option>
          <option value="failed">Failed</option>
          <option value="error">Not scored</option>
        </select>
      </label>
      <DataTable
        caption={`Items of the run of ${run.candidate_model}`}
        columns={columns}
        rows={items.data}
        getRowId={(i) => i.id}
        isLoading={items.isLoading}
        density="compact"
        error={items.isError ? { title: "Unable to load results", detail: errorMessage(items.error, "Unknown error"), onRetry: () => void items.refetch() } : null}
        empty={{ title: "Nothing to show", detail: isRunActive(run.status) ? "Results appear as items finish." : "No items match this filter." }}
        footer={
          offset > 0 || (items.data?.length ?? 0) === PAGE_SIZE ? (
            <div className="flex gap-2">
              <button type="button" className="btn-outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                Previous
              </button>
              <button type="button" className="btn-outline" disabled={(items.data?.length ?? 0) < PAGE_SIZE} onClick={() => setOffset(offset + PAGE_SIZE)}>
                Next
              </button>
            </div>
          ) : undefined
        }
      />
    </div>
  );
}

export function EvalRunsPage() {
  const { token, user } = useAuth();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const isAdmin = user?.role === "admin";
  // Arriving from a draft prompt ("Run an eval of this prompt") opens the start form with that template chosen.
  const [params, setParams] = useSearchParams();
  const presetTemplate = params.get("template") ?? undefined;
  const [starting, setStarting] = useState(Boolean(presetTemplate));
  const [openId, setOpenId] = useState<string | null>(null);

  const runs = useQuery({
    queryKey: ["eval-runs", token],
    queryFn: () => apiClient.get<EvalRun[]>(`${RUNS}?limit=50`, token!),
    enabled: Boolean(token) && isAdmin,
    // Poll only while something is running, so an idle page makes no requests.
    refetchInterval: (query) => ((query.state.data ?? []).some((r) => isRunActive(r.status)) ? POLL_MS : false),
  });

  const cancel = useMutation({
    mutationFn: (id: string) => apiClient.post<EvalRun>(`${RUNS}/${id}/cancel`, {}, token!),
    onSuccess: () => {
      toast.success("Run cancelled. Items already in flight will finish.");
      void qc.invalidateQueries({ queryKey: ["eval-runs"] });
    },
    onError: (error) => toast.error(errorMessage(error, "Could not cancel the run")),
  });

  const columns: Column<EvalRun>[] = [
    { key: "status", header: "Status", cell: (r) => <RunBadge status={r.status} /> },
    { key: "model", header: "Model", mono: true, cell: (r) => r.candidate_model },
    { key: "progress", header: "Progress", align: "right", mono: true, cell: (r) => `${r.completed_items} / ${r.total_items}` },
    { key: "pass", header: "Pass rate", align: "right", mono: true, cell: (r) => percent(r.pass_rate) },
    { key: "cost", header: "Cost", align: "right", mono: true, cell: (r) => `${money(r.cost_usd)} of ${money(r.max_cost_usd)}` },
    { key: "created", header: "Started", nowrap: true, cell: (r) => formatDate(r.created_at) },
    {
      key: "actions",
      header: "Actions",
      cell: (r) =>
        isRunActive(r.status) ? (
          <button
            type="button"
            className="btn-icon-only"
            aria-label={`Cancel the run of ${r.candidate_model}`}
            onClick={async (e) => {
              e.stopPropagation();
              const ok = await confirm({ title: "Cancel this run?", description: "No new item will start. Items already in flight finish and are kept.", confirmLabel: "Cancel run", destructive: true });
              if (ok) cancel.mutate(r.id);
            }}
          >
            <Square size={14} className="text-accent-amber" aria-hidden />
          </button>
        ) : null,
    },
  ];

  if (!isAdmin) {
    return (
      <section className="page-wrap">
        <PageHeader title="Eval runs" description="Score a model on a dataset." />
        <p role="note">You need admin privileges to manage eval runs.</p>
      </section>
    );
  }

  return (
    <section className="page-wrap">
      <PageHeader
        title="Eval runs"
        description="Send a dataset through a model and score the answers. Use it to compare a prompt or a model before you ship it."
        actions={
          <button type="button" onClick={() => setStarting(true)} className="flex items-center gap-1.5 bg-accent-sky">
            <Plus size={15} aria-hidden />
            Start a run
          </button>
        }
      />
      <DataTable
        caption="Eval runs"
        columns={columns}
        rows={runs.data}
        getRowId={(r) => r.id}
        isLoading={runs.isLoading}
        error={runs.isError ? { title: "Unable to load runs", detail: errorMessage(runs.error, "Unknown error"), onRetry: () => void runs.refetch() } : null}
        empty={{ title: "No runs yet", detail: "Create a dataset and an evaluator, then start a run." }}
        onRowClick={(r) => setOpenId(openId === r.id ? null : r.id)}
        getRowLabel={(r) => `run of ${r.candidate_model}`}
        expandedId={openId}
        renderExpanded={(r) => <RunDetail run={r} />}
      />
      {starting ? (
        <NewRunDialog
          initialTemplateId={presetTemplate}
          onClose={() => {
            setStarting(false);
            if (presetTemplate) setParams({}, { replace: true });
          }}
        />
      ) : null}
    </section>
  );
}
