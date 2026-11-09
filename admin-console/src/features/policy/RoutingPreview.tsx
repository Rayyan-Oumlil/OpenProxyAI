import { useId, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type { DataClass, PolicyPreviewRequest, PolicyPreviewResponse, PolicyPreviewVerdict } from "../../api/types";
import { Badge } from "../../components/ui/badge";
import { Fact } from "../../components/ui/Fact";
import { DATA_CLASSES, describeDataClass } from "../../lib/dataClasses";
import { EXCLUSION_TEXT, routingOutcome } from "../../lib/routing";

const VERDICT: Record<PolicyPreviewVerdict, { label: string; variant: "success" | "warning" | "error" }> = {
  allowed: { label: "Would be served", variant: "success" },
  blocked_by_policy: { label: "Blocked by policy", variant: "error" },
  blocked_by_routing: { label: "Refused by routing", variant: "error" },
  would_block_if_enforced: { label: "Would be refused if routing were enforced", variant: "warning" },
};

const NOT_CHECKED: Record<string, string> = {
  rate_limit: "rate limits",
  budget: "budgets",
  cache: "the cache",
  experiments: "experiments",
  tool_taint: "tool taint",
  upstream: "the provider call",
};

/** Ask the gateway what would happen to a request, without sending it. It uses the saved policy, not unsaved edits. */
export function RoutingPreview({ token, unsaved }: { token: string; unsaved: boolean }) {
  const ids = { model: useId(), prompt: useId(), cls: useId(), fallback: useId() };
  const [model, setModel] = useState("");
  const [prompt, setPrompt] = useState("");
  const [dataClass, setDataClass] = useState<DataClass | "">("");
  const [fallback, setFallback] = useState("");

  const preview = useMutation({
    mutationFn: (body: PolicyPreviewRequest) => apiClient.post<PolicyPreviewResponse>("/api/v1/policy/preview", body, token),
    onError: (err) => toast.error(err instanceof Error ? err.message : "Preview failed"),
  });

  // Not a <form>: this panel sits inside the policy page's save form, where Enter would save the policy.
  function run() {
    if (!model.trim() || !prompt.trim()) {
      toast.error("Enter a model and a prompt to preview.");
      return;
    }
    preview.mutate({
      model: model.trim(),
      messages: [{ role: "user", content: prompt }],
      ...(dataClass ? { data_class: dataClass } : {}),
      ...(fallback.trim() ? { fallback_model: fallback.trim() } : {}),
    });
  }

  function enterRuns(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      run();
    }
  }

  const result = preview.data;
  return (
    <section className="surface-panel stack-form" aria-labelledby={`${ids.model}-title`}>
      <h2 id={`${ids.model}-title`} style={{ fontSize: "1rem", fontWeight: 600 }}>
        Preview a request
      </h2>
      <p className="muted" style={{ fontSize: "0.88rem" }}>
        See what the gateway would do with a request before it does it. Nothing is sent to a provider, logged or counted. It uses the policy as saved
        {unsaved ? ", so your unsaved changes are not included until you save." : "."}
      </p>
      <div className="stack-form">
        <label className="inline-control" htmlFor={ids.model}>
          Model
          <input id={ids.model} type="text" value={model} onChange={(e) => setModel(e.target.value)} onKeyDown={enterRuns} placeholder="openai/gpt-4o, or cap:CODE_GENERATION" autoComplete="off" />
        </label>
        <label className="inline-control" htmlFor={ids.prompt}>
          Prompt
          <textarea id={ids.prompt} rows={3} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Paste a prompt, for example one containing an SSN" />
        </label>
        <label className="inline-control" htmlFor={ids.cls}>
          Data class the caller asserts (optional)
          <select id={ids.cls} value={dataClass} onChange={(e) => setDataClass(e.target.value as DataClass | "")}>
            <option value="">None</option>
            {DATA_CLASSES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
        <label className="inline-control" htmlFor={ids.fallback}>
          Fallback model (optional)
          <input id={ids.fallback} type="text" value={fallback} onChange={(e) => setFallback(e.target.value)} onKeyDown={enterRuns} placeholder="openai/gpt-4o-mini" autoComplete="off" />
        </label>
        <div>
          <button type="button" onClick={run} disabled={preview.isPending} style={{ background: "var(--accent-sky)" }}>
            {preview.isPending ? "Checking…" : "Preview"}
          </button>
        </div>
      </div>

      <div aria-live="polite">
        {result ? (
          <div className="stack-form">
            <p>
              <Badge variant={VERDICT[result.verdict].variant}>{VERDICT[result.verdict].label}</Badge>
            </p>
            <dl className="trace-facts">
              <Fact label="Data class">{describeDataClass(result.data_class.class, result.data_class.source, result.data_class.entities)}</Fact>
              <Fact label="Policy">
                {result.policy.allowed
                  ? `Allowed (policy mode: ${result.policy.mode})`
                  : `Blocked: ${result.policy.reason_code ?? "policy"}${result.policy.detail ? `. ${result.policy.detail}` : ""}`}
              </Fact>
              <Fact label="Routing">
                {routingOutcome(result.routing)}
                {result.routing.key_alias ? <span className="trace-fact__detail"> · through key {result.routing.key_alias}</span> : null}
                {result.routing.model === null && result.routing.authorized.length > 0 ? (
                  <span className="trace-fact__detail"> · authorized for this request: {result.routing.authorized.join(", ")}</span>
                ) : null}
                <span className="trace-fact__detail"> · routing is currently {result.routing.current_mode.replace("_", " ")}</span>
              </Fact>
              {Object.keys(result.routing.excluded).length > 0 ? (
                <Fact label="Ruled out">
                  {Object.entries(result.routing.excluded).map(([name, code]) => (
                    <div key={name}>
                      {name}: {EXCLUSION_TEXT[code] ?? code}
                    </div>
                  ))}
                </Fact>
              ) : null}
              {result.fallback ? (
                <Fact label="Fallback">
                  {result.fallback.model}: {result.fallback.authorized ? "allowed" : `refused (${result.fallback.reason})`}
                </Fact>
              ) : null}
            </dl>
            <p className="muted" style={{ fontSize: "0.82rem" }}>
              Not checked here: {result.not_evaluated.map((k) => NOT_CHECKED[k] ?? k).join(", ")}.
            </p>
          </div>
        ) : null}
      </div>
    </section>
  );
}
