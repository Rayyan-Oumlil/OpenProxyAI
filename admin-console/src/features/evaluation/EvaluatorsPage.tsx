import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type { Evaluator, EvaluatorType } from "../../api/evaluationTypes";
import { Badge } from "../../components/ui/badge";
import { useConfirm } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../../components/ui/dialog";
import { PageHeader } from "../../components/ui/PageHeader";
import { EVALUATOR_HELP, EVALUATOR_LABEL } from "../../lib/evaluation";
import { formatDate } from "../../lib/utils";
import { useAuth } from "../../state/AuthContext";

const EVALUATORS = "/api/v1/evaluators";
const TYPES: EvaluatorType[] = ["exact", "regex", "llm_judge"];

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

/** A one-line description of an evaluator's settings for the table. */
export function describeConfig(e: Pick<Evaluator, "type" | "config">): string {
  const c = e.config;
  if (e.type === "exact") return `${c.case_sensitive ? "case-sensitive" : "ignores case"}, ${c.strip === false ? "exact whitespace" : "ignores surrounding whitespace"}`;
  if (e.type === "regex") return `${c.mode === "fullmatch" ? "must match fully" : "must contain"} /${String(c.pattern)}/${c.ignore_case ? "i" : ""}`;
  return `${String(c.model)}, ${c.scale === "pass_fail" ? "pass or fail" : `1 to 5, passes at ${String(c.pass_threshold)}`}`;
}

function NewEvaluatorDialog({ onClose }: { onClose: () => void }) {
  const { token } = useAuth();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [type, setType] = useState<EvaluatorType>("exact");
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [pattern, setPattern] = useState("");
  const [mode, setMode] = useState<"search" | "fullmatch">("search");
  const [ignoreCase, setIgnoreCase] = useState(false);
  const [model, setModel] = useState("");
  const [criteria, setCriteria] = useState("");
  const [scale, setScale] = useState<"1-5" | "pass_fail">("1-5");
  const [threshold, setThreshold] = useState("4");

  const create = useMutation({
    mutationFn: (body: { name: string; type: EvaluatorType; config: Record<string, unknown> }) => apiClient.post<Evaluator>(EVALUATORS, body, token!),
    onSuccess: () => {
      toast.success("Evaluator created.");
      void qc.invalidateQueries({ queryKey: ["evaluators"] });
      onClose();
    },
    // The server explains what is wrong with the config (a bad pattern, a missing model); show it as it says it.
    onError: (error) => toast.error(errorMessage(error, "Could not create the evaluator")),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return toast.error("Give the evaluator a name.");
    const config: Record<string, unknown> =
      type === "exact"
        ? { case_sensitive: caseSensitive }
        : type === "regex"
          ? { pattern, mode, ignore_case: ignoreCase }
          : { model: model.trim(), criteria, scale, ...(scale === "1-5" ? { pass_threshold: Number(threshold) } : {}) };
    create.mutate({ name: name.trim(), type, config });
  }

  return (
    <Dialog open onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New evaluator</DialogTitle>
          <DialogDescription>{EVALUATOR_HELP[type]}</DialogDescription>
        </DialogHeader>
        <form className="stack-form" onSubmit={submit}>
          <label className="inline-control">
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} placeholder="e.g. helpful-judge" />
          </label>
          <label className="inline-control">
            Type
            <select value={type} onChange={(e) => setType(e.target.value as EvaluatorType)}>
              {TYPES.map((t) => (
                <option key={t} value={t}>
                  {EVALUATOR_LABEL[t]}
                </option>
              ))}
            </select>
          </label>

          {type === "exact" ? (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={caseSensitive} onChange={(e) => setCaseSensitive(e.target.checked)} />
              Case-sensitive
            </label>
          ) : null}

          {type === "regex" ? (
            <>
              <label className="inline-control">
                Pattern (up to 200 characters)
                <input value={pattern} onChange={(e) => setPattern(e.target.value)} maxLength={200} placeholder="^Bonjour" />
              </label>
              <label className="inline-control">
                Match
                <select value={mode} onChange={(e) => setMode(e.target.value as "search" | "fullmatch")}>
                  <option value="search">Anywhere in the answer</option>
                  <option value="fullmatch">The whole answer</option>
                </select>
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={ignoreCase} onChange={(e) => setIgnoreCase(e.target.checked)} />
                Ignore case
              </label>
            </>
          ) : null}

          {type === "llm_judge" ? (
            <>
              <label className="inline-control">
                Judge model
                <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="openai/gpt-4o-mini" />
              </label>
              <label className="inline-control">
                Criteria: what is a good answer?
                <textarea className="textarea-short" value={criteria} onChange={(e) => setCriteria(e.target.value)} rows={3} maxLength={2000} />
              </label>
              <div className="flex gap-3">
                <label className="inline-control">
                  Scale
                  <select value={scale} onChange={(e) => setScale(e.target.value as "1-5" | "pass_fail")}>
                    <option value="1-5">1 to 5</option>
                    <option value="pass_fail">Pass or fail</option>
                  </select>
                </label>
                {scale === "1-5" ? (
                  <label className="inline-control">
                    Passes at
                    <select value={threshold} onChange={(e) => setThreshold(e.target.value)}>
                      {[1, 2, 3, 4, 5].map((n) => (
                        <option key={n} value={n}>
                          {n} or higher
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
              </div>
            </>
          ) : null}

          <DialogFooter>
            <button type="button" className="btn-outline" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" disabled={create.isPending} className="bg-accent-sky">
              Create evaluator
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function EvaluatorsPage() {
  const { token, user } = useAuth();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const isAdmin = user?.role === "admin";
  const [creating, setCreating] = useState(false);

  const evaluators = useQuery({
    queryKey: ["evaluators", token],
    queryFn: () => apiClient.get<Evaluator[]>(EVALUATORS, token!),
    enabled: Boolean(token) && isAdmin,
  });

  const remove = useMutation({
    mutationFn: (id: string) => apiClient.del<void>(`${EVALUATORS}/${id}`, token!),
    onSuccess: () => {
      toast.success("Evaluator deleted.");
      void qc.invalidateQueries({ queryKey: ["evaluators"] });
    },
    onError: (error) => toast.error(errorMessage(error, "Could not delete the evaluator")),
  });

  const columns: Column<Evaluator>[] = [
    { key: "name", header: "Name", cell: (e) => <span className="font-medium">{e.name}</span> },
    { key: "type", header: "Type", cell: (e) => <Badge variant="policy">{EVALUATOR_LABEL[e.type]}</Badge> },
    { key: "config", header: "Settings", cell: (e) => <span className="text-sm">{describeConfig(e)}</span> },
    { key: "created", header: "Created", nowrap: true, cell: (e) => formatDate(e.created_at) },
    {
      key: "actions",
      header: "Actions",
      cell: (e) => (
        <button
          type="button"
          className="btn-icon-only"
          aria-label={`Delete evaluator ${e.name}`}
          onClick={async () => {
            const ok = await confirm({ title: "Delete evaluator?", description: `Finished runs keep a copy of “${e.name}” and stay readable.`, confirmLabel: "Delete evaluator", destructive: true });
            if (ok) remove.mutate(e.id);
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
        <PageHeader title="Evaluators" description="How an answer is scored." />
        <p role="note">You need admin privileges to manage evaluators.</p>
      </section>
    );
  }

  return (
    <section className="page-wrap">
      <PageHeader
        title="Evaluators"
        description="How an answer is scored: exact match, a regular expression, or another model acting as judge."
        actions={
          <button type="button" onClick={() => setCreating(true)} className="flex items-center gap-1.5 bg-accent-sky">
            <Plus size={15} aria-hidden />
            New evaluator
          </button>
        }
      />
      <DataTable
        caption="Evaluators"
        columns={columns}
        rows={evaluators.data}
        getRowId={(e) => e.id}
        isLoading={evaluators.isLoading}
        error={evaluators.isError ? { title: "Unable to load evaluators", detail: errorMessage(evaluators.error, "Unknown error"), onRetry: () => void evaluators.refetch() } : null}
        empty={{ title: "No evaluators", detail: "Create one to score answers in an eval run." }}
      />
      {creating ? <NewEvaluatorDialog onClose={() => setCreating(false)} /> : null}
    </section>
  );
}
