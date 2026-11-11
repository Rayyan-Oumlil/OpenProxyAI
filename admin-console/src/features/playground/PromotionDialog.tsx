import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type { PromoteResponse, PromotionStatus, RunSummary } from "../../api/evaluationTypes";
import type { PromptTemplate } from "../../api/types";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../../components/ui/dialog";
import { percent } from "../../lib/evaluation";

export const MIN_OVERRIDE_REASON = 10;

function describeRun(run: RunSummary): string {
  return `${run.scored_items} of ${run.total_items} items scored, ${percent(run.pass_rate)} passed (${run.status})`;
}

export function PromotionDialog({ template, isAdmin, token, onClose }: { template: PromptTemplate; isAdmin: boolean; token: string; onClose: () => void }) {
  const qc = useQueryClient();
  const [override, setOverride] = useState(false);
  const [reason, setReason] = useState("");

  const status = useQuery({
    queryKey: ["prompt-promotion", template.id],
    queryFn: () => apiClient.get<PromotionStatus>(`/api/v1/prompt-templates/${template.id}/promotion`, token),
  });

  const promote = useMutation({
    mutationFn: () => apiClient.post<PromoteResponse>(`/api/v1/prompt-templates/${template.id}/promote`, override ? { override: true, reason: reason.trim() } : {}, token),
    onSuccess: (done) => {
      toast.success(done.overridden ? `v${done.version} is live (override recorded).` : `v${done.version} is live.`);
      void qc.invalidateQueries({ queryKey: ["prompt-templates"] });
      onClose();
    },
    // The server explains exactly what is missing; show it rather than a generic failure.
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not promote this prompt"),
  });

  const view = status.data;
  const reasonTooShort = override && reason.trim().length < MIN_OVERRIDE_REASON;
  const canPromote = isAdmin && view !== undefined && (view.passes_gate || override) && !reasonTooShort;

  return (
    <Dialog open onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Promote “{template.name}” v{template.version}</DialogTitle>
          <DialogDescription>Make this draft the live version. The version it replaces is retired.</DialogDescription>
        </DialogHeader>

        {status.isLoading ? <p className="text-muted">Checking…</p> : null}
        {status.isError ? <p className="text-accent-rose">{status.error instanceof Error ? status.error.message : "Could not check this prompt"}</p> : null}

        {view ? (
          <div className="stack-form">
            {!view.gate_enabled ? (
              <p role="status" className="text-sm">
                The promotion gate is off for this organization, so nothing has to pass. Turn it on under Policy, Evaluation.
              </p>
            ) : view.passes_gate ? (
              <p role="status" className="text-sm">
                <strong>Ready.</strong> {view.qualifying_run ? `An eval run vouches for this exact prompt: ${describeRun(view.qualifying_run)}.` : null}
              </p>
            ) : (
              <div role="status" className="stack-form">
                <p className="text-sm">
                  <strong>Not ready.</strong> A run must pass at {percent(view.requirements.min_pass_rate)} over at least {view.requirements.min_items} scored items.
                </p>
                <ul className="text-sm" style={{ listStyle: "disc", paddingLeft: 18 }}>
                  {view.reasons.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
                {view.best_run ? <p className="text-muted text-sm">Closest run: {describeRun(view.best_run)}.</p> : null}
                <p className="text-sm">
                  <Link to={`/eval-runs?template=${template.id}`} onClick={onClose}>
                    Run an eval of this prompt
                  </Link>
                </p>
              </div>
            )}

            {isAdmin && view.gate_enabled && !view.passes_gate ? (
              <fieldset className="stack-form">
                <legend className="text-sm font-medium">Override</legend>
                <label className="flex items-start gap-2 text-sm">
                  <input type="checkbox" checked={override} onChange={(e) => setOverride(e.target.checked)} />
                  <span>Promote anyway. This is recorded in the audit log with your reason.</span>
                </label>
                {override ? (
                  <label className="inline-control">
                    Reason (at least {MIN_OVERRIDE_REASON} characters)
                    <textarea className="textarea-short" value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={500} />
                  </label>
                ) : null}
              </fieldset>
            ) : null}

            {!isAdmin ? <p className="text-muted text-sm">Only an admin can promote a prompt.</p> : null}
          </div>
        ) : null}

        <DialogFooter>
          <button type="button" className="btn-outline" onClick={onClose}>
            Close
          </button>
          {isAdmin ? (
            <button type="button" disabled={!canPromote || promote.isPending} className="bg-accent-sky" onClick={() => promote.mutate()}>
              {override ? "Promote with override" : "Promote"}
            </button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
