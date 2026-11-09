import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { X, Plus, Trash2, Shield, Landmark, Building2, ChevronDown, ChevronUp } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type { ApplyTemplateRequest, OrganizationResponse, PolicyConfigRequest, PolicyTemplate } from "../../api/types";
import { LoadingState } from "../../components/LoadingState";
import { PageHeader } from "../../components/ui/PageHeader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/Tabs";
import { DataRoutingTab } from "./DataRoutingTab";
import { ErrorState } from "../../components/ErrorState";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
import { useAuth } from "../../state/AuthContext";

const TEMPLATE_ICONS: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  healthcare_hipaa: Shield,
  finance_pci: Landmark,
  government_fedramp: Building2,
};

const TEMPLATE_LABELS: Record<string, string> = {
  healthcare_hipaa: "Healthcare (HIPAA)",
  finance_pci: "Finance (PCI-DSS)",
  government_fedramp: "Government (FedRAMP)",
};

const PII_ENTITIES = [
  "EMAIL_ADDRESS",
  "PHONE_NUMBER",
  "CREDIT_CARD",
  "US_SSN",
  "PERSON",
  "LOCATION",
  "URL",
  "IBAN_CODE",
  "IP_ADDRESS",
];

const DEFAULT_POLICY: PolicyConfigRequest = {
  enforcement_mode: "off",
  allowed_models: [],
  blocked_keywords: [],
  pii_detection_enabled: false,
  pii_entities: [],
  model_rate_limits: {},
  prompt_injection_detection_enabled: false,
  response_guardrails_enabled: false,
  response_pii_redact: false,
  default_data_class: "internal",
  data_class_map: {},
  routing_mode: "off",
  max_risk_rating: "high",
};

function TagInput({
  tags,
  onChange,
  placeholder,
  label,
  disabled = false,
}: {
  tags: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  /** Names the field for assistive technology; the visible placeholder disappears once a tag exists. */
  label: string;
  disabled?: boolean;
}) {
  const [input, setInput] = useState("");

  function addTag(value: string) {
    const trimmed = value.trim();
    if (trimmed && !tags.includes(trimmed)) {
      onChange([...tags, trimmed]);
    }
    setInput("");
  }

  function removeTag(tag: string) {
    onChange(tags.filter((t) => t !== tag));
  }

  return (
    <div
      role="group"
      aria-label={label}
      className="tag-input"
      style={{
        border: "1px solid var(--line)",
        borderRadius: 12,
        padding: "0.5rem 0.6rem",
        background: "var(--surface)",
        display: "flex",
        flexWrap: "wrap",
        gap: "0.35rem",
        minHeight: 42,
        alignItems: "center",
      }}
    >
      {tags.map((tag) => (
        <span
          key={tag}
          className="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs"
          style={{ background: "color-mix(in srgb, var(--accent) 14%, transparent)", color: "var(--text)", border: "1px solid color-mix(in srgb, var(--accent) 40%, transparent)" }}
        >
          {tag}
          {disabled ? null : (
            <button
              type="button"
              onClick={() => removeTag(tag)}
              aria-label={`Remove ${tag}`}
              style={{ border: "none", background: "transparent", padding: 0, cursor: "pointer", lineHeight: 1, color: "inherit" }}
            >
              <X size={10} aria-hidden />
            </button>
          )}
        </span>
      ))}
      <input
        type="text"
        aria-label={label}
        disabled={disabled}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            addTag(input);
          }
          if (e.key === "Backspace" && !input && tags.length > 0) {
            onChange(tags.slice(0, -1));
          }
        }}
        onBlur={() => { if (input) addTag(input); }}
        placeholder={tags.length === 0 ? placeholder : ""}
        style={{
          border: "none",
          outline: "none",
          background: "transparent",
          fontSize: "0.88rem",
          minWidth: 120,
          flex: 1,
          padding: "2px 0",
        }}
      />
      {input && (
        <button
          type="button"
          onClick={() => addTag(input)}
          aria-label={`Add ${label}`}
          style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--text)" }}
        >
          <Plus size={13} aria-hidden />
        </button>
      )}
    </div>
  );
}

function extractPolicy(org: OrganizationResponse): PolicyConfigRequest {
  const raw = org.settings?.policy as Partial<PolicyConfigRequest> | undefined;
  if (!raw) return { ...DEFAULT_POLICY };
  return {
    enforcement_mode: raw.enforcement_mode ?? "off",
    allowed_models: raw.allowed_models ?? [],
    blocked_keywords: raw.blocked_keywords ?? [],
    pii_detection_enabled: raw.pii_detection_enabled ?? false,
    pii_entities: raw.pii_entities ?? [],
    model_rate_limits: raw.model_rate_limits ?? {},
    prompt_injection_detection_enabled: raw.prompt_injection_detection_enabled ?? false,
    response_guardrails_enabled: raw.response_guardrails_enabled ?? false,
    response_pii_redact: raw.response_pii_redact ?? false,
    default_data_class: raw.default_data_class ?? "internal",
    data_class_map: raw.data_class_map ?? {},
    routing_mode: raw.routing_mode ?? "off",
    max_risk_rating: raw.max_risk_rating ?? "high",
  };
}

function TemplateCard({
  template,
  isApplied,
  isAdmin,
  isEligible,
  onApply,
  isApplying,
}: {
  template: PolicyTemplate;
  isApplied: boolean;
  isAdmin: boolean;
  isEligible: boolean;
  onApply: () => void;
  isApplying: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const Icon = TEMPLATE_ICONS[template.name] ?? Shield;
  const label = TEMPLATE_LABELS[template.name] ?? template.name;

  return (
    <div
      className="rounded-xl border p-4"
      style={{
        borderColor: "var(--line)",
        background: isApplied ? "color-mix(in srgb, var(--accent) 8%, transparent)" : "var(--surface)",
      }}
    >
      <div className="flex items-start gap-3">
        <div
          className="rounded-lg p-2 shrink-0"
          style={{ background: "color-mix(in srgb, var(--accent) 14%, transparent)", color: "var(--accent)" }}
        >
          <Icon size={20} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 style={{ fontSize: "0.95rem", fontWeight: 600 }}>{label}</h3>
            {isApplied && (
              <span
                className="text-xs px-2 py-0.5 rounded-full"
                style={{ background: "color-mix(in srgb, var(--ok) 14%, transparent)", color: "var(--ok)" }}
              >
                Applied
              </span>
            )}
          </div>
          <p className="muted" style={{ fontSize: "0.82rem", marginTop: 4 }}>
            {template.description}
          </p>
          <button
            type="button"
            onClick={() => setExpanded((e) => !e)}
            className="flex items-center gap-1 mt-2 text-sm"
            style={{ color: "var(--accent-sky)", background: "none", border: "none", cursor: "pointer" }}
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            What it configures
          </button>
          {expanded && (
            <ul className="mt-2 pl-4 text-sm text-muted space-y-1" style={{ listStyle: "disc" }}>
              {template.configures.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          )}
          {isAdmin && (
            isEligible ? (
              <button
                type="button"
                onClick={onApply}
                disabled={isApplying}
                style={{
                  marginTop: 12,
                  padding: "0.4rem 0.8rem",
                  fontSize: "0.85rem",
                  borderRadius: 8,
                  background: "var(--accent-sky)",
                  color: "var(--accent-ink)",
                  border: "none",
                  cursor: isApplying ? "not-allowed" : "pointer",
                }}
              >
                {isApplying ? "Applying…" : "Apply Template"}
              </button>
            ) : (
              <span
                className="inline-block mt-3 text-xs px-2 py-1 rounded-full"
                style={{ background: "color-mix(in srgb, var(--warn) 14%, transparent)", color: "var(--warn)" }}
              >
                Requires Starter plan
              </span>
            )
          )}
        </div>
      </div>
    </div>
  );
}

type ModelRateLimit = { model: string; rpm: string; tpm: string };

function ModelRateLimitsSection({
  limits,
  onChange,
  disabled,
}: {
  limits: Record<string, { rpm?: number; tpm?: number }>;
  onChange: (limits: Record<string, { rpm?: number; tpm?: number }>) => void;
  disabled: boolean;
}) {
  const [newRow, setNewRow] = useState<ModelRateLimit>({ model: "", rpm: "", tpm: "" });

  const entries = Object.entries(limits);

  function addRow() {
    const model = newRow.model.trim();
    if (!model) return;
    onChange({
      ...limits,
      [model]: {
        rpm: newRow.rpm ? parseInt(newRow.rpm, 10) : undefined,
        tpm: newRow.tpm ? parseInt(newRow.tpm, 10) : undefined,
      },
    });
    setNewRow({ model: "", rpm: "", tpm: "" });
  }

  function removeRow(model: string) {
    const next = { ...limits };
    delete next[model];
    onChange(next);
  }

  return (
    <div className="stack-form">
      {entries.length > 0 && (
        <table className="data-table" style={{ fontSize: "0.85rem" }}>
          <thead>
            <tr>
              <th>Model</th>
              <th>RPM</th>
              <th>TPM</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {entries.map(([model, v]) => (
              <tr key={model}>
                <td><code>{model}</code></td>
                <td>{v.rpm ?? "—"}</td>
                <td>{v.tpm ?? "—"}</td>
                <td>
                  <button
                    type="button"
                    onClick={() => removeRow(model)}
                    disabled={disabled}
                    style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--muted)" }}
                  >
                    <Trash2 size={13} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {!disabled && (
        <div className="flex gap-2 flex-wrap items-end">
          <div className="flex flex-col gap-1">
            <span style={{ fontSize: "0.78rem", color: "var(--muted)" }}>Model</span>
            <input
              type="text"
              value={newRow.model}
              onChange={(e) => setNewRow((r) => ({ ...r, model: e.target.value }))}
              placeholder="openai/gpt-4o"
              style={{ width: 180 }}
            />
          </div>
          <div className="flex flex-col gap-1">
            <span style={{ fontSize: "0.78rem", color: "var(--muted)" }}>RPM</span>
            <input
              type="number"
              value={newRow.rpm}
              onChange={(e) => setNewRow((r) => ({ ...r, rpm: e.target.value }))}
              placeholder="60"
              style={{ width: 90 }}
            />
          </div>
          <div className="flex flex-col gap-1">
            <span style={{ fontSize: "0.78rem", color: "var(--muted)" }}>TPM</span>
            <input
              type="number"
              value={newRow.tpm}
              onChange={(e) => setNewRow((r) => ({ ...r, tpm: e.target.value }))}
              placeholder="100000"
              style={{ width: 110 }}
            />
          </div>
          <button
            type="button"
            onClick={addRow}
            style={{ background: "var(--accent-sky)", color: "var(--accent-ink)", alignSelf: "flex-end" }}
          >
            <Plus size={13} /> Add
          </button>
        </div>
      )}
    </div>
  );
}

export function PolicyConfigPage() {
  const { token, user } = useAuth();
  const qc = useQueryClient();
  const isAdmin = user?.role === "admin";

  const orgQuery = useQuery({
    queryKey: ["organizations", "current", token],
    queryFn: () => apiClient.get<OrganizationResponse>("/api/v1/organizations/current", token!),
    enabled: Boolean(token),
  });

  const [form, setForm] = useState<PolicyConfigRequest>({ ...DEFAULT_POLICY });

  // Hydrate the form when the organization loads or changes (state adjusted while rendering, not in an effect)
  const [hydratedFrom, setHydratedFrom] = useState<OrganizationResponse | undefined>();
  if (orgQuery.data && orgQuery.data !== hydratedFrom) {
    setHydratedFrom(orgQuery.data);
    setForm(extractPolicy(orgQuery.data));
  }

  const saveMutation = useMutation({
    mutationFn: (data: PolicyConfigRequest) =>
      apiClient.patch("/api/v1/organizations/current/policy", data, token!),
    onSuccess: () => {
      toast.success("Policy configuration saved.");
      qc.invalidateQueries({ queryKey: ["organizations", "current"] });
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to save policy"),
  });

  const templatesQuery = useQuery({
    queryKey: ["policy", "templates", token],
    queryFn: () => apiClient.get<PolicyTemplate[]>("/api/v1/organizations/current/policy/templates", token!),
    enabled: Boolean(token),
  });

  const applyTemplateMutation = useMutation({
    mutationFn: (data: ApplyTemplateRequest) =>
      apiClient.post("/api/v1/organizations/current/policy/apply-template", data, token!),
    onSuccess: () => {
      toast.success("Compliance template applied.");
      qc.invalidateQueries({ queryKey: ["organizations", "current"] });
      setConfirmTemplate(null);
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to apply template"),
  });

  const currentTemplate = (orgQuery.data?.settings?.policy as { metadata?: { template?: string } } | undefined)
    ?.metadata?.template;

  const [confirmTemplate, setConfirmTemplate] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    saveMutation.mutate(form);
  }

  const [tab, setTab] = useState("enforcement");
  // Unsaved changes: the form against what the server last returned.
  const serverPolicy = orgQuery.data ? extractPolicy(orgQuery.data) : null;
  const dirty = serverPolicy !== null && JSON.stringify(serverPolicy) !== JSON.stringify(form);

  if (orgQuery.isLoading) return <LoadingState label="Loading policy configuration…" />;
  if (orgQuery.isError)
    return (
      <ErrorState
        title="Unable to load policy"
        detail={orgQuery.error instanceof Error ? orgQuery.error.message : "Unknown error"}
      />
    );

  const hasTemplates = Boolean(templatesQuery.data && templatesQuery.data.length > 0);

  return (
    <section className="page-wrap">
      <PageHeader title="Policy configuration" description="What the gateway allows, blocks, redacts and limits for every request in this organization." />

      {!isAdmin && (
        <div
          className="rounded-xl px-4 py-3 text-sm"
          style={{ background: "color-mix(in srgb, var(--warn) 14%, transparent)", color: "var(--warn)" }}
          role="status"
        >
          You need admin privileges to modify policy settings.
        </div>
      )}

      <Dialog open={confirmTemplate !== null} onOpenChange={(open) => !open && setConfirmTemplate(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Apply compliance template</DialogTitle>
            <DialogDescription>
              This will override your current policy settings. Your model allowlist and rate limits will be preserved.
              Continue?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button
              type="button"
              onClick={() => setConfirmTemplate(null)}
              style={{ padding: "0.5rem 1rem", borderRadius: 8, border: "1px solid var(--line)" }}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                if (confirmTemplate) {
                  applyTemplateMutation.mutate({ template: confirmTemplate as ApplyTemplateRequest["template"] });
                }
              }}
              disabled={applyTemplateMutation.isPending}
              style={{ background: "var(--accent-sky)", color: "var(--accent-ink)", padding: "0.5rem 1rem", borderRadius: 8 }}
            >
              {applyTemplateMutation.isPending ? "Applying…" : "Apply Template"}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <form onSubmit={handleSubmit} className="policy-form">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList aria-label="Policy sections">
            <TabsTrigger value="enforcement">Enforcement</TabsTrigger>
            <TabsTrigger value="data">Data protection</TabsTrigger>
            <TabsTrigger value="routing">Data and routing</TabsTrigger>
            <TabsTrigger value="limits">Rate limits</TabsTrigger>
            <TabsTrigger value="templates">Templates</TabsTrigger>
          </TabsList>

          <TabsContent value="enforcement" className="stack-form">
            {/* Enforcement Mode */}
            <section className="surface-panel stack-form">
              <h2 style={{ fontSize: "1rem", fontWeight: 600 }}>Enforcement Mode</h2>
              <p className="muted" style={{ fontSize: "0.88rem" }}>
                Controls how policy violations are handled globally.
              </p>
              <div className="flex flex-col gap-2">
                {(["observe", "log_only", "enforce"] as const).map((mode) => (
                  <label key={mode} className="flex items-start gap-2.5 cursor-pointer">
                    <input
                      type="radio"
                      name="enforcement_mode"
                      value={mode}
                      checked={form.enforcement_mode === mode}
                      onChange={() => setForm((f) => ({ ...f, enforcement_mode: mode }))}
                      disabled={!isAdmin}
                      style={{ marginTop: 3 }}
                    />
                    <div>
                      <span className="font-medium" style={{ fontSize: "0.9rem" }}>
                        {mode === "observe" && "Observe"}
                        {mode === "log_only" && "Log Only"}
                        {mode === "enforce" && "Enforce"}
                      </span>
                      <p style={{ color: "var(--muted)", fontSize: "0.82rem", margin: "1px 0 0" }}>
                        {mode === "observe" && "Evaluate rules but never block or log policy events."}
                        {mode === "log_only" && "Log policy events but never block requests."}
                        {mode === "enforce" && "Block requests that violate policy rules."}
                      </p>
                    </div>
                  </label>
                ))}
              </div>
            </section>

            {/* Model Allowlist */}
            <section className="surface-panel stack-form">
              <h2 style={{ fontSize: "1rem", fontWeight: 600 }}>Model Allowlist</h2>
              <p className="muted" style={{ fontSize: "0.88rem" }}>
                If empty, all models are allowed. Press Enter or comma to add a model.
              </p>
              <TagInput
                tags={form.allowed_models ?? []}
                onChange={(tags) => setForm((f) => ({ ...f, allowed_models: tags }))}
                label="Allowed models"
                disabled={!isAdmin}
                placeholder="gpt-4o, claude-3-5-sonnet-20241022…"
              />
            </section>

            {/* Blocked Keywords */}
            <section className="surface-panel stack-form">
              <h2 style={{ fontSize: "1rem", fontWeight: 600 }}>Blocked Keywords</h2>
              <p className="muted" style={{ fontSize: "0.88rem" }}>
                Requests containing these words/phrases will be flagged or blocked.
              </p>
              <TagInput
                tags={form.blocked_keywords ?? []}
                onChange={(tags) => setForm((f) => ({ ...f, blocked_keywords: tags }))}
                label="Blocked keywords"
                disabled={!isAdmin}
                placeholder="confidential, password, ssn…"
              />
            </section>
          </TabsContent>

          <TabsContent value="data" className="stack-form">
            {/* PII Detection */}
            <section className="surface-panel stack-form">
              <h2 style={{ fontSize: "1rem", fontWeight: 600 }}>PII Detection</h2>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={form.pii_detection_enabled}
                  onChange={(e) => setForm((f) => ({ ...f, pii_detection_enabled: e.target.checked }))}
                  disabled={!isAdmin}
                />
                <span style={{ fontSize: "0.9rem" }}>Enable PII Detection</span>
              </label>

              {form.pii_detection_enabled && (
                <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", marginTop: "0.5rem" }}>
                  {PII_ENTITIES.map((entity) => (
                    <label key={entity} className="check-row">
                      <input
                        type="checkbox"
                        checked={(form.pii_entities ?? []).includes(entity)}
                        onChange={(e) =>
                          setForm((f) => ({
                            ...f,
                            pii_entities: e.target.checked
                              ? [...(f.pii_entities ?? []), entity]
                              : (f.pii_entities ?? []).filter((x) => x !== entity),
                          }))
                        }
                        disabled={!isAdmin}
                      />
                      <span style={{ fontSize: "0.85rem" }}>{entity}</span>
                    </label>
                  ))}
                </div>
              )}
            </section>

            {/* Advanced Guardrails */}
            <section className="surface-panel stack-form">
              <h2 style={{ fontSize: "1rem", fontWeight: 600 }}>Advanced Guardrails</h2>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={form.prompt_injection_detection_enabled ?? false}
                  onChange={(e) => setForm((f) => ({ ...f, prompt_injection_detection_enabled: e.target.checked }))}
                  disabled={!isAdmin}
                />
                <div>
                  <span style={{ fontSize: "0.9rem" }}>Prompt Injection Detection</span>
                  <p style={{ color: "var(--muted)", fontSize: "0.82rem", margin: "1px 0 0" }}>
                    Blocks jailbreak patterns (ignore instructions, DAN mode, act as, etc.)
                  </p>
                </div>
              </label>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={form.response_guardrails_enabled ?? false}
                  onChange={(e) => setForm((f) => ({ ...f, response_guardrails_enabled: e.target.checked }))}
                  disabled={!isAdmin}
                />
                <div>
                  <span style={{ fontSize: "0.9rem" }}>Response Guardrails</span>
                  <p style={{ color: "var(--muted)", fontSize: "0.82rem", margin: "1px 0 0" }}>
                    Evaluate LLM responses against policy rules before returning them.
                  </p>
                </div>
              </label>
              {form.response_guardrails_enabled && (
                <label className="check-row" style={{ marginLeft: "1.75rem" }}>
                  <input
                    type="checkbox"
                    checked={form.response_pii_redact ?? false}
                    onChange={(e) => setForm((f) => ({ ...f, response_pii_redact: e.target.checked }))}
                    disabled={!isAdmin}
                  />
                  <div>
                    <span style={{ fontSize: "0.9rem" }}>Redact PII instead of blocking</span>
                    <p style={{ color: "var(--muted)", fontSize: "0.82rem", margin: "1px 0 0" }}>
                      Replace detected PII with [REDACTED] rather than blocking the response entirely.
                    </p>
                  </div>
                </label>
              )}
            </section>
          </TabsContent>

          <TabsContent value="routing" className="stack-form">
            <DataRoutingTab form={form} setForm={(update) => setForm(update)} isAdmin={isAdmin} unsaved={dirty} token={token!} />
          </TabsContent>

          <TabsContent value="limits" className="stack-form">
            {/* Per-Model Rate Limits */}
            <section className="surface-panel stack-form">
              <h2 style={{ fontSize: "1rem", fontWeight: 600 }}>Per-Model Rate Limits</h2>
              <p className="muted" style={{ fontSize: "0.88rem" }}>
                Override global RPM/TPM limits for specific models. Leave empty to use org-level limits.
              </p>
              <ModelRateLimitsSection
                limits={form.model_rate_limits ?? {}}
                onChange={(limits) => setForm((f) => ({ ...f, model_rate_limits: limits }))}
                disabled={!isAdmin}
              />
            </section>
          </TabsContent>

          <TabsContent value="templates" className="stack-form">
            {hasTemplates ? (
    <section className="surface-panel stack-form">
              <h2 style={{ fontSize: "1rem", fontWeight: 600 }}>Quick Setup</h2>
              <p className="muted" style={{ fontSize: "0.88rem" }}>
                Apply a pre-built compliance template to configure guardrails for your industry.
              </p>
              <div
                className="grid gap-4"
                style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}
              >
                {(templatesQuery.data ?? []).map((tpl) => (
                  <TemplateCard
                    key={tpl.name}
                    template={tpl}
                    isApplied={currentTemplate === tpl.name}
                    isAdmin={isAdmin}
                    isEligible={orgQuery.data?.plan !== "free"}
                    onApply={() => setConfirmTemplate(tpl.name)}
                    isApplying={applyTemplateMutation.isPending && confirmTemplate === tpl.name}
                  />
                ))}
              </div>
            </section>
            ) : (
              <p className="trace-note">No compliance templates are available for this organization.</p>
            )}
          </TabsContent>
        </Tabs>

        {isAdmin && (
          <div className="policy-savebar">
            <span className="policy-savebar__status" role="status">
              {dirty ? "You have unsaved changes." : "All changes saved."}
            </span>
            <button
              type="button"
              className="btn-outline"
              disabled={!dirty || saveMutation.isPending}
              onClick={() => serverPolicy && setForm(serverPolicy)}
            >
              Discard
            </button>
            <button type="submit" disabled={!dirty || saveMutation.isPending} style={{ background: "var(--accent-sky)" }}>
              {saveMutation.isPending ? "Saving…" : "Save policy"}
            </button>
          </div>
        )}
      </form>
    </section>
  );
}
