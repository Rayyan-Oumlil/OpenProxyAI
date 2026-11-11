import { useId } from "react";

import type { PolicyConfigRequest } from "../../api/types";

type SetForm = (update: (form: PolicyConfigRequest) => PolicyConfigRequest) => void;

/** 0.25 -> "25". Whole percents only: that is all the control offers, and it keeps the stored rate readable. */
export function ratePercent(rate: number | undefined): string {
  return String(Math.round((rate ?? 0) * 100));
}

function clampPercent(text: string, min: number, max: number): number {
  const n = Math.round(Number(text));
  return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : min;
}

export function EvaluationTab({ form, setForm, isAdmin }: { form: PolicyConfigRequest; setForm: SetForm; isAdmin: boolean }) {
  const ids = { rate: useId(), gate: useId(), pass: useId(), items: useId() };
  const rate = form.payload_capture_sample_rate ?? 0;
  const capturing = rate > 0;
  const gate = form.prompt_promotion_gate ?? false;

  return (
    <>
      <section className="stack-form" aria-labelledby={`${ids.rate}-h`}>
        <h2 id={`${ids.rate}-h`}>Capture traffic for evaluation</h2>
        <p className="text-muted text-sm">
          To judge a change you need real examples. Capturing keeps a redacted copy of a share of your prompts and answers, and nothing else is stored of what users typed. It is{" "}
          <strong>off by default</strong>.
        </p>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={capturing}
            disabled={!isAdmin}
            onChange={(e) => setForm((f) => ({ ...f, payload_capture_sample_rate: e.target.checked ? 0.1 : 0 }))}
          />
          Keep a sample of delivered requests
        </label>
        {capturing ? (
          <label className="inline-control" htmlFor={ids.rate} style={{ maxWidth: 260 }}>
            Share of requests kept (%)
            <input
              id={ids.rate}
              type="number"
              min={1}
              max={100}
              value={ratePercent(rate)}
              disabled={!isAdmin}
              onChange={(e) => setForm((f) => ({ ...f, payload_capture_sample_rate: clampPercent(e.target.value, 1, 100) / 100 }))}
            />
          </label>
        ) : null}
        <ul className="text-sm text-muted" style={{ listStyle: "disc", paddingLeft: 18 }}>
          <li>Personal data (email addresses, SSNs, card numbers) is replaced before anything is written, and the row is flagged so datasets refuse it.</li>
          <li>Requests classified above the operator's ceiling (default Internal) are never kept, whatever the rate.</li>
          <li>Each row expires with your plan's audit retention.</li>
        </ul>
      </section>

      <section className="stack-form" aria-labelledby={`${ids.gate}-h`}>
        <h2 id={`${ids.gate}-h`}>Prompt promotion gate</h2>
        <p className="text-muted text-sm">
          With the gate on, editing a prompt template makes a <em>draft</em>. A draft goes live only when an eval run of that exact prompt passes, or an admin overrides with a written reason that is audited. Off by default: edits go live
          straight away.
        </p>
        <label className="flex items-center gap-2 text-sm">
          <input
            id={ids.gate}
            type="checkbox"
            checked={gate}
            disabled={!isAdmin}
            onChange={(e) => setForm((f) => ({ ...f, prompt_promotion_gate: e.target.checked }))}
          />
          Require a passing eval run before a prompt goes live
        </label>
        {gate ? (
          <div className="flex gap-3">
            <label className="inline-control" htmlFor={ids.pass}>
              Pass rate required (%)
              <input
                id={ids.pass}
                type="number"
                min={1}
                max={100}
                value={ratePercent(form.prompt_gate_min_pass_rate ?? 0.8)}
                disabled={!isAdmin}
                onChange={(e) => setForm((f) => ({ ...f, prompt_gate_min_pass_rate: clampPercent(e.target.value, 1, 100) / 100 }))}
              />
            </label>
            <label className="inline-control" htmlFor={ids.items}>
              Items the run must score
              <input
                id={ids.items}
                type="number"
                min={1}
                value={form.prompt_gate_min_items ?? 10}
                disabled={!isAdmin}
                onChange={(e) => setForm((f) => ({ ...f, prompt_gate_min_items: Math.max(1, Math.round(Number(e.target.value)) || 1) }))}
              />
            </label>
          </div>
        ) : null}
        <p className="text-muted text-sm">
          A run counts only if it completed, tested this exact prompt (editing the draft afterwards invalidates it), scored enough items, passed at the required rate, and no more than a tenth of its items errored.
        </p>
      </section>
    </>
  );
}
