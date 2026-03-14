import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { X, Plus } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type { OrganizationResponse, PolicyConfigRequest } from "../../api/types";
import { LoadingState } from "../../components/LoadingState";
import { ErrorState } from "../../components/ErrorState";
import { useAuth } from "../../state/AuthContext";

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
  enforcement_mode: "observe",
  allowed_models: [],
  blocked_keywords: [],
  pii_detection_enabled: false,
  pii_entities: [],
};

function TagInput({
  tags,
  onChange,
  placeholder,
}: {
  tags: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
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
      style={{
        border: "1px solid var(--line)",
        borderRadius: 12,
        padding: "0.5rem 0.6rem",
        background: "#fff",
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
          style={{ background: "rgba(14,165,233,0.1)", color: "#0369a1" }}
        >
          {tag}
          <button
            type="button"
            onClick={() => removeTag(tag)}
            style={{ border: "none", background: "transparent", padding: 0, cursor: "pointer", lineHeight: 1 }}
          >
            <X size={10} />
          </button>
        </span>
      ))}
      <input
        type="text"
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
          style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--accent-sky)" }}
        >
          <Plus size={13} />
        </button>
      )}
    </div>
  );
}

function extractPolicy(org: OrganizationResponse): PolicyConfigRequest {
  const raw = org.settings?.policy as Partial<PolicyConfigRequest> | undefined;
  if (!raw) return { ...DEFAULT_POLICY };
  return {
    enforcement_mode: raw.enforcement_mode ?? "observe",
    allowed_models: raw.allowed_models ?? [],
    blocked_keywords: raw.blocked_keywords ?? [],
    pii_detection_enabled: raw.pii_detection_enabled ?? false,
    pii_entities: raw.pii_entities ?? [],
  };
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

  // Hydrate form once org loads
  useEffect(() => {
    if (orgQuery.data) {
      setForm(extractPolicy(orgQuery.data));
    }
  }, [orgQuery.data]);

  const saveMutation = useMutation({
    mutationFn: (data: PolicyConfigRequest) =>
      apiClient.patch("/api/v1/organizations/current/policy", data, token!),
    onSuccess: () => {
      toast.success("Policy configuration saved.");
      qc.invalidateQueries({ queryKey: ["organizations", "current"] });
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to save policy"),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    saveMutation.mutate(form);
  }

  if (orgQuery.isLoading) return <LoadingState label="Loading policy configuration…" />;
  if (orgQuery.isError)
    return (
      <ErrorState
        title="Unable to load policy"
        detail={orgQuery.error instanceof Error ? orgQuery.error.message : "Unknown error"}
      />
    );

  return (
    <section className="page-wrap">
      <header className="page-header">
        <p className="eyebrow">Gateway Governance</p>
        <h1>Policy Configuration</h1>
      </header>

      {!isAdmin && (
        <div
          className="rounded-xl px-4 py-3 text-sm"
          style={{ background: "rgba(245,158,11,0.1)", color: "#92400e" }}
        >
          You need admin privileges to modify policy settings.
        </div>
      )}

      <form onSubmit={handleSubmit} className="stack-form">
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
            tags={form.allowed_models}
            onChange={(tags) => setForm((f) => ({ ...f, allowed_models: tags }))}
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
            tags={form.blocked_keywords}
            onChange={(tags) => setForm((f) => ({ ...f, blocked_keywords: tags }))}
            placeholder="confidential, password, ssn…"
          />
        </section>

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
                    checked={form.pii_entities.includes(entity)}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        pii_entities: e.target.checked
                          ? [...f.pii_entities, entity]
                          : f.pii_entities.filter((x) => x !== entity),
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

        {isAdmin && (
          <button
            type="submit"
            disabled={saveMutation.isPending}
            style={{ background: "var(--accent-sky)", alignSelf: "flex-start" }}
          >
            {saveMutation.isPending ? "Saving…" : "Save Policy"}
          </button>
        )}
      </form>
    </section>
  );
}
