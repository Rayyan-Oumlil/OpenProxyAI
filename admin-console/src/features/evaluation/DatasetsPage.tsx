import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type { Dataset, DatasetItem, ImportRequest, ImportResponse } from "../../api/evaluationTypes";
import { Badge } from "../../components/ui/badge";
import { useConfirm } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../../components/ui/dialog";
import { PageHeader } from "../../components/ui/PageHeader";
import { previewOf, toIso } from "../../lib/evaluation";
import { formatDate } from "../../lib/utils";
import { useAuth } from "../../state/AuthContext";

const DATASETS = "/api/v1/datasets";
const PAGE_SIZE = 50;

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function NewDatasetDialog({ open, onClose, onCreate, busy }: { open: boolean; onClose: () => void; onCreate: (name: string, description: string) => void; busy: boolean }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  return (
    <Dialog open={open} onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New dataset</DialogTitle>
          <DialogDescription>A named set of prompts to test a model or a prompt against.</DialogDescription>
        </DialogHeader>
        <form
          className="stack-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (!name.trim()) return toast.error("Give the dataset a name.");
            onCreate(name.trim(), description.trim());
          }}
        >
          <label className="inline-control">
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} placeholder="e.g. support-regressions" />
          </label>
          <label className="inline-control">
            Description (optional)
            <input value={description} onChange={(e) => setDescription(e.target.value)} maxLength={500} />
          </label>
          <DialogFooter>
            <button type="button" className="btn-outline" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" disabled={busy} className="bg-accent-sky">
              Create dataset
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ImportDialog({ dataset, onClose }: { dataset: Dataset; onClose: () => void }) {
  const { token } = useAuth();
  const qc = useQueryClient();
  const [model, setModel] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [scoreName, setScoreName] = useState("");
  const [minScore, setMinScore] = useState("");
  const [maxScore, setMaxScore] = useState("");
  const [limit, setLimit] = useState("100");
  const [order, setOrder] = useState<"latest" | "random">("latest");
  const [result, setResult] = useState<ImportResponse | null>(null);

  const importMutation = useMutation({
    mutationFn: (body: ImportRequest) => apiClient.post<ImportResponse>(`${DATASETS}/${dataset.id}/import`, body, token!),
    onSuccess: (response) => {
      setResult(response);
      void qc.invalidateQueries({ queryKey: ["datasets"] });
      void qc.invalidateQueries({ queryKey: ["dataset-items", dataset.id] });
    },
    onError: (error) => toast.error(errorMessage(error, "Import failed")),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const body: ImportRequest = { limit: Number(limit) || 100, order };
    if (model.trim()) body.model = model.trim();
    if (toIso(since)) body.since = toIso(since);
    if (toIso(until)) body.until = toIso(until);
    if (scoreName.trim()) {
      body.score_name = scoreName.trim();
      if (minScore !== "") body.min_score = Number(minScore);
      if (maxScore !== "") body.max_score = Number(maxScore);
    } else if (minScore !== "" || maxScore !== "") {
      return toast.error("A score range needs a score name, for example thumbs.");
    }
    setResult(null);
    importMutation.mutate(body);
  }

  return (
    <Dialog open onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Import into {dataset.name}</DialogTitle>
          <DialogDescription>
            Copies redacted prompts and answers from captured traffic. Requests where personal data was found are never imported.
          </DialogDescription>
        </DialogHeader>
        <form className="stack-form" onSubmit={submit}>
          <label className="inline-control">
            Model (optional)
            <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="e.g. openai/gpt-4o-mini" />
          </label>
          <div className="flex gap-3">
            <label className="inline-control">
              From
              <input type="datetime-local" value={since} onChange={(e) => setSince(e.target.value)} />
            </label>
            <label className="inline-control">
              Until
              <input type="datetime-local" value={until} onChange={(e) => setUntil(e.target.value)} />
            </label>
          </div>
          <div className="flex gap-3">
            <label className="inline-control">
              Feedback score (optional)
              <input value={scoreName} onChange={(e) => setScoreName(e.target.value)} placeholder="thumbs" />
            </label>
            <label className="inline-control">
              At least
              <input type="number" step="any" value={minScore} onChange={(e) => setMinScore(e.target.value)} placeholder="1" />
            </label>
            <label className="inline-control">
              At most
              <input type="number" step="any" value={maxScore} onChange={(e) => setMaxScore(e.target.value)} />
            </label>
          </div>
          <div className="flex gap-3">
            <label className="inline-control">
              How many (1 to 1000)
              <input type="number" min={1} max={1000} value={limit} onChange={(e) => setLimit(e.target.value)} />
            </label>
            <label className="inline-control">
              Pick
              <select value={order} onChange={(e) => setOrder(e.target.value as "latest" | "random")}>
                <option value="latest">Most recent</option>
                <option value="random">Random sample</option>
              </select>
            </label>
          </div>
          {result ? (
            <p role="status" className="text-sm">
              Imported <strong>{result.imported}</strong>. Skipped {result.skipped_redacted} with personal data and {result.skipped_duplicate} already in this dataset.
              {result.stopped_at_capacity ? " The dataset is full." : ""}
            </p>
          ) : null}
          <DialogFooter>
            <button type="button" className="btn-outline" onClick={onClose}>
              Close
            </button>
            <button type="submit" disabled={importMutation.isPending} className="bg-accent-sky">
              Import
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function AddItemForm({ dataset }: { dataset: Dataset }) {
  const { token } = useAuth();
  const qc = useQueryClient();
  const [prompt, setPrompt] = useState("");
  const [expected, setExpected] = useState("");

  const add = useMutation({
    mutationFn: (item: { prompt: string; expected: string }) =>
      apiClient.post<DatasetItem>(
        `${DATASETS}/${dataset.id}/items`,
        { messages: [{ role: "user", content: item.prompt }], ...(item.expected.trim() ? { expected: item.expected } : {}) },
        token!,
      ),
    onSuccess: (_saved, item) => {
      // Clear a field only if it still holds what was just saved: the user may already be typing the next item.
      setPrompt((current) => (current === item.prompt ? "" : current));
      setExpected((current) => (current === item.expected ? "" : current));
      void qc.invalidateQueries({ queryKey: ["datasets"] });
      void qc.invalidateQueries({ queryKey: ["dataset-items", dataset.id] });
    },
    onError: (error) => toast.error(errorMessage(error, "Could not add the item")),
  });

  return (
    <form
      className="stack-form"
      aria-label={`Add an item to ${dataset.name}`}
      onSubmit={(e) => {
        e.preventDefault();
        if (!prompt.trim()) return toast.error("Write the prompt first.");
        add.mutate({ prompt, expected });
      }}
    >
      <label className="inline-control">
        Prompt
        <textarea className="textarea-short" value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={2} />
      </label>
      <label className="inline-control">
        Expected answer (optional, used by the exact-match evaluator and shown to a judge)
        <input value={expected} onChange={(e) => setExpected(e.target.value)} />
      </label>
      <div>
        <button type="submit" disabled={add.isPending} className="flex items-center gap-1.5 bg-accent-sky">
          <Plus size={14} aria-hidden />
          Add item
        </button>
      </div>
    </form>
  );
}

function DatasetDetail({ dataset }: { dataset: Dataset }) {
  const { token } = useAuth();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [offset, setOffset] = useState(0);
  const [importing, setImporting] = useState(false);

  const items = useQuery({
    queryKey: ["dataset-items", dataset.id, offset],
    queryFn: () => apiClient.get<DatasetItem[]>(`${DATASETS}/${dataset.id}/items?limit=${PAGE_SIZE}&offset=${offset}`, token!),
    enabled: Boolean(token),
  });

  const removeItem = useMutation({
    mutationFn: (id: string) => apiClient.del<void>(`${DATASETS}/${dataset.id}/items/${id}`, token!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["datasets"] });
      void qc.invalidateQueries({ queryKey: ["dataset-items", dataset.id] });
    },
    onError: (error) => toast.error(errorMessage(error, "Could not delete the item")),
  });

  const columns: Column<DatasetItem>[] = [
    { key: "prompt", header: "Prompt", cell: (i) => <span className="text-sm">{previewOf(i.messages)}</span> },
    { key: "expected", header: "Expected", cell: (i) => (i.expected ? <span className="text-sm">{i.expected}</span> : <span className="text-muted">—</span>) },
    { key: "source", header: "Source", cell: (i) => <Badge variant="muted">{i.request_id ? "Captured" : "Written"}</Badge> },
    {
      key: "actions",
      header: "Actions",
      cell: (i) => (
        <button
          type="button"
          className="btn-icon-only"
          aria-label={`Delete item: ${previewOf(i.messages, 30)}`}
          onClick={async () => {
            const ok = await confirm({ title: "Delete this item?", description: "It is removed from the dataset. Past runs keep their results.", confirmLabel: "Delete item", destructive: true });
            if (ok) removeItem.mutate(i.id);
          }}
        >
          <Trash2 size={14} className="text-accent-rose" aria-hidden />
        </button>
      ),
    },
  ];

  const rows = items.data ?? [];
  return (
    <div className="stack-form" style={{ padding: "12px 4px" }}>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Items in {dataset.name}</h3>
        <button type="button" className="btn-outline flex items-center gap-1.5" onClick={() => setImporting(true)}>
          <Download size={14} aria-hidden />
          Import from traffic
        </button>
      </div>
      <DataTable
        caption={`Items in ${dataset.name}`}
        columns={columns}
        rows={items.data}
        getRowId={(i) => i.id}
        isLoading={items.isLoading}
        density="compact"
        error={items.isError ? { title: "Unable to load items", detail: errorMessage(items.error, "Unknown error"), onRetry: () => void items.refetch() } : null}
        empty={{ title: "No items yet", detail: "Add a prompt below, or import captured traffic." }}
        footer={
          offset > 0 || rows.length === PAGE_SIZE ? (
            <div className="flex gap-2">
              <button type="button" className="btn-outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                Previous
              </button>
              <button type="button" className="btn-outline" disabled={rows.length < PAGE_SIZE} onClick={() => setOffset(offset + PAGE_SIZE)}>
                Next
              </button>
            </div>
          ) : undefined
        }
      />
      <AddItemForm dataset={dataset} />
      {importing ? <ImportDialog dataset={dataset} onClose={() => setImporting(false)} /> : null}
    </div>
  );
}

export function DatasetsPage() {
  const { token, user } = useAuth();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const isAdmin = user?.role === "admin";
  const [creating, setCreating] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  const datasets = useQuery({
    queryKey: ["datasets", token],
    queryFn: () => apiClient.get<Dataset[]>(DATASETS, token!),
    enabled: Boolean(token) && isAdmin,
  });

  const create = useMutation({
    mutationFn: (v: { name: string; description: string }) => apiClient.post<Dataset>(DATASETS, { name: v.name, ...(v.description ? { description: v.description } : {}) }, token!),
    onSuccess: (created) => {
      toast.success("Dataset created.");
      setCreating(false);
      setOpenId(created.id);
      void qc.invalidateQueries({ queryKey: ["datasets"] });
    },
    onError: (error) => toast.error(errorMessage(error, "Could not create the dataset")),
  });

  const remove = useMutation({
    mutationFn: (id: string) => apiClient.del<void>(`${DATASETS}/${id}`, token!),
    onSuccess: () => {
      toast.success("Dataset deleted.");
      void qc.invalidateQueries({ queryKey: ["datasets"] });
    },
    onError: (error) => toast.error(errorMessage(error, "Could not delete the dataset")),
  });

  const columns: Column<Dataset>[] = [
    { key: "name", header: "Name", cell: (d) => <span className="font-medium">{d.name}</span> },
    { key: "description", header: "Description", cell: (d) => (d.description ? <span className="text-sm">{d.description}</span> : <span className="text-muted">—</span>) },
    { key: "items", header: "Items", align: "right", mono: true, cell: (d) => d.item_count },
    { key: "created", header: "Created", nowrap: true, cell: (d) => formatDate(d.created_at) },
    {
      key: "actions",
      header: "Actions",
      cell: (d) => (
        <button
          type="button"
          className="btn-icon-only"
          aria-label={`Delete dataset ${d.name}`}
          onClick={async (e) => {
            e.stopPropagation();
            const ok = await confirm({ title: "Delete dataset?", description: `“${d.name}” and its ${d.item_count} items will be removed. Finished runs keep their results.`, confirmLabel: "Delete dataset", destructive: true });
            if (ok) remove.mutate(d.id);
          }}
        >
          <Trash2 size={14} className="text-accent-rose" aria-hidden />
        </button>
      ),
    },
  ];

  if (!isAdmin) {
    return (
      <section className="page-wrap">
        <PageHeader title="Datasets" description="Sets of prompts to test models and prompts against." />
        <p role="note">You need admin privileges to manage datasets.</p>
      </section>
    );
  }

  return (
    <section className="page-wrap">
      <PageHeader
        title="Datasets"
        description="Sets of prompts to test models and prompts against. Build them from captured traffic or write them by hand. Personal data never enters a dataset."
        actions={
          <button type="button" onClick={() => setCreating(true)} className="flex items-center gap-1.5 bg-accent-sky">
            <Plus size={15} aria-hidden />
            New dataset
          </button>
        }
      />
      <DataTable
        caption="Datasets"
        columns={columns}
        rows={datasets.data}
        getRowId={(d) => d.id}
        isLoading={datasets.isLoading}
        error={datasets.isError ? { title: "Unable to load datasets", detail: errorMessage(datasets.error, "Unknown error"), onRetry: () => void datasets.refetch() } : null}
        empty={{ title: "No datasets", detail: "Create one, then add prompts or import captured traffic. Capturing is off until you set a sample rate on the Policy page." }}
        onRowClick={(d) => setOpenId(openId === d.id ? null : d.id)}
        getRowLabel={(d) => d.name}
        expandedId={openId}
        renderExpanded={(d) => <DatasetDetail dataset={d} />}
      />
      {creating ? <NewDatasetDialog open onClose={() => setCreating(false)} onCreate={(name, description) => create.mutate({ name, description })} busy={create.isPending} /> : null}
    </section>
  );
}
