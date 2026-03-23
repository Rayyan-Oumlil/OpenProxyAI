import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Play, Plus, Pencil, Trash2, Beaker, FileText } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type {
  PromptTemplate,
  PlaygroundCompareResult,
  PlaygroundCompareResponse,
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
import { formatCost, formatLatency, cn } from "../../lib/utils";

const COMMON_MODELS = [
  "openai/gpt-4o",
  "openai/gpt-4o-mini",
  "anthropic/claude-sonnet-4-6",
  "anthropic/claude-haiku-4-5-20251001",
  "anthropic/claude-3-5-sonnet-20241022",
  "anthropic/claude-3-5-haiku-20241022",
  "google/gemini-1.5-pro",
  "google/gemini-1.5-flash",
  "mistral/mistral-large-latest",
  "mistral/mistral-small-latest",
];

type TabId = "compare" | "templates";

function CompareTab({
  token,
  loadedTemplate,
  onClearTemplate,
}: {
  token: string;
  loadedTemplate: PromptTemplate | null;
  onClearTemplate: () => void;
}) {
  const [models, setModels] = useState<string[]>([
    "anthropic/claude-haiku-4-5-20251001",
  ]);
  const [systemMessage, setSystemMessage] = useState("");
  const [userMessage, setUserMessage] = useState("");

  useEffect(() => {
    if (loadedTemplate) {
      setSystemMessage(loadedTemplate.system_message ?? "");
      setUserMessage(loadedTemplate.user_template);
      onClearTemplate();
    }
  }, [loadedTemplate, onClearTemplate]);
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState<number | "">(1024);
  const [results, setResults] = useState<PlaygroundCompareResult[] | null>(null);

  const compareMutation = useMutation({
    mutationFn: (data: Parameters<typeof apiClient.compareModels>[0]) =>
      apiClient.compareModels(data, token),
    onSuccess: (data: PlaygroundCompareResponse) => {
      setResults(data.results);
      toast.success("Comparison complete");
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Comparison failed");
    },
  });

  function toggleModel(model: string) {
    setModels((prev) => {
      if (prev.includes(model)) {
        const next = prev.filter((m) => m !== model);
        return next.length >= 2 ? next : prev;
      }
      if (prev.length >= 4) return prev;
      return [...prev, model];
    });
  }

  function handleRun() {
    if (!userMessage.trim()) {
      toast.error("User message is required");
      return;
    }
    const messages =
      systemMessage.trim().length > 0
        ? [
            { role: "system", content: systemMessage.trim() },
            { role: "user", content: userMessage.trim() },
          ]
        : [{ role: "user", content: userMessage.trim() }];

    compareMutation.mutate({
      models,
      messages,
      temperature: temperature,
      max_tokens: typeof maxTokens === "number" ? maxTokens : undefined,
    });
  }

  return (
    <div className="stack-form" style={{ gap: "1.5rem" }}>
      <div className="surface-panel" style={{ padding: "1rem" }}>
        <label className="block text-sm font-medium mb-2" style={{ color: "var(--muted)" }}>
          Models (select 2–4)
        </label>
        <div className="flex flex-wrap gap-2">
          {COMMON_MODELS.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => toggleModel(m)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-sm transition-colors border",
                models.includes(m)
                  ? "bg-[var(--accent-sky)] text-white border-[var(--accent-sky)]"
                  : "border-[var(--line)] hover:bg-[rgba(44,109,191,0.08)]"
              )}
            >
              {m.split("/")[1]}
            </button>
          ))}
        </div>
      </div>

      <div className="surface-panel" style={{ padding: "1rem" }}>
        <label className="block text-sm font-medium mb-2" style={{ color: "var(--muted)" }}>
          System message (optional)
        </label>
        <textarea
          value={systemMessage}
          onChange={(e) => setSystemMessage(e.target.value)}
          placeholder="You are a helpful assistant..."
          rows={3}
          className="w-full rounded-lg border px-3 py-2 text-sm"
          style={{ borderColor: "var(--line)", background: "var(--bg)" }}
        />
      </div>

      <div className="surface-panel" style={{ padding: "1rem" }}>
        <label className="block text-sm font-medium mb-2" style={{ color: "var(--muted)" }}>
          User message
        </label>
        <textarea
          value={userMessage}
          onChange={(e) => setUserMessage(e.target.value)}
          placeholder="Enter your prompt... Use {{variable}} for placeholders"
          rows={5}
          className="w-full rounded-lg border px-3 py-2 text-sm font-mono"
          style={{ borderColor: "var(--line)", background: "var(--bg)" }}
        />
      </div>

      <div className="flex flex-wrap gap-6 items-center">
        <div>
          <label className="block text-sm font-medium mb-1" style={{ color: "var(--muted)" }}>
            Temperature: {temperature.toFixed(1)}
          </label>
          <input
            type="range"
            min={0}
            max={2}
            step={0.1}
            value={temperature}
            onChange={(e) => setTemperature(parseFloat(e.target.value))}
            className="w-40"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1" style={{ color: "var(--muted)" }}>
            Max tokens
          </label>
          <input
            type="number"
            min={1}
            max={128000}
            value={maxTokens}
            onChange={(e) =>
              setMaxTokens(e.target.value === "" ? "" : parseInt(e.target.value, 10))
            }
            className="w-28 rounded border px-2 py-1 text-sm"
            style={{ borderColor: "var(--line)" }}
          />
        </div>
        <button
          type="button"
          onClick={handleRun}
          disabled={compareMutation.isPending}
          className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium"
          style={{
            background: "var(--accent-sky)",
            color: "#fff",
          }}
        >
          <Play size={16} />
          {compareMutation.isPending ? "Running..." : "Run"}
        </button>
      </div>

      {compareMutation.isPending && (
        <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${models.length}, 1fr)` }}>
          {models.map((m) => (
            <div
              key={m}
              className="surface-panel p-4 rounded-lg animate-pulse"
              style={{ minHeight: 200 }}
            >
              <div className="h-4 bg-[var(--line)] rounded w-1/2 mb-3" />
              <div className="h-3 bg-[var(--line)] rounded w-full mb-2" />
              <div className="h-3 bg-[var(--line)] rounded w-4/5 mb-2" />
              <div className="h-3 bg-[var(--line)] rounded w-3/4" />
            </div>
          ))}
        </div>
      )}

      {results && !compareMutation.isPending && (
        <div
          className="grid gap-4"
          style={{ gridTemplateColumns: `repeat(${results.length}, 1fr)` }}
        >
          {results.map((r) => (
            <div
              key={r.model}
              className="surface-panel p-4 rounded-lg flex flex-col"
              style={{
                minHeight: 200,
                borderColor: r.error ? "var(--accent-rose)" : "var(--line)",
                borderWidth: r.error ? 2 : 1,
              }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-sm truncate">{r.model.split("/")[1]}</span>
                {r.error && (
                  <Badge variant="error" className="text-xs">
                    Error
                  </Badge>
                )}
              </div>
              <div className="flex-1 overflow-auto text-sm mb-3" style={{ color: "var(--text)" }}>
                {r.error ? (
                  <p style={{ color: "var(--accent-rose)" }}>{r.error}</p>
                ) : (
                  <pre className="whitespace-pre-wrap font-sans">{r.content}</pre>
                )}
              </div>
              {!r.error && (
                <div className="flex flex-wrap gap-2 text-xs" style={{ color: "var(--muted)" }}>
                  <span>{r.prompt_tokens + r.completion_tokens} tokens</span>
                  <span>{formatCost(r.cost_usd)}</span>
                  <span>{formatLatency(r.latency_ms)}</span>
                  {r.ttft_ms != null && <span>TTFT: {formatLatency(r.ttft_ms)}</span>}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TemplatesTab({
  token,
  onSelectTemplate,
}: {
  token: string;
  onSelectTemplate?: (t: PromptTemplate) => void;
}) {
  const queryClient = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    system_message: "",
    user_template: "",
  });

  const templatesQuery = useQuery({
    queryKey: ["prompt-templates", token],
    queryFn: () => apiClient.getPromptTemplates(token!),
    enabled: Boolean(token),
  });

  const createMutation = useMutation({
    mutationFn: (data: Parameters<typeof apiClient.createPromptTemplate>[0]) =>
      apiClient.createPromptTemplate(data, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompt-templates"] });
      toast.success("Template created");
      setShowModal(false);
      setFormData({ name: "", description: "", system_message: "", user_template: "" });
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed to create template");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof apiClient.updatePromptTemplate>[1] }) =>
      apiClient.updatePromptTemplate(id, data, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompt-templates"] });
      toast.success("Template updated");
      setEditingId(null);
      setFormData({ name: "", description: "", system_message: "", user_template: "" });
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed to update template");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.deletePromptTemplate(id, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompt-templates"] });
      toast.success("Template deleted");
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed to delete template");
    },
  });

  function openCreate() {
    setFormData({ name: "", description: "", system_message: "", user_template: "" });
    setEditingId(null);
    setShowModal(true);
  }

  function openEdit(t: PromptTemplate) {
    setFormData({
      name: t.name,
      description: t.description ?? "",
      system_message: t.system_message ?? "",
      user_template: t.user_template,
    });
    setEditingId(t.id);
    setShowModal(true);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!formData.name.trim() || !formData.user_template.trim()) {
      toast.error("Name and user template are required");
      return;
    }
    if (editingId) {
      updateMutation.mutate({
        id: editingId,
        data: {
          name: formData.name.trim(),
          description: formData.description.trim() || null,
          system_message: formData.system_message.trim() || null,
          user_template: formData.user_template.trim(),
        },
      });
    } else {
      createMutation.mutate({
        name: formData.name.trim(),
        description: formData.description.trim() || null,
        system_message: formData.system_message.trim() || null,
        user_template: formData.user_template.trim(),
      });
    }
  }

  const canManage = useAuth().user?.role === "admin" || useAuth().user?.role === "developer";

  if (templatesQuery.isLoading) return <LoadingState label="Loading templates..." />;
  if (templatesQuery.isError) {
    return (
      <ErrorState
        title="Unable to load templates"
        detail={templatesQuery.error instanceof Error ? templatesQuery.error.message : "Unknown error"}
      />
    );
  }

  const templates = templatesQuery.data ?? [];

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
          Save and reuse prompts with {"{{variable}}"} placeholders
        </p>
        {canManage && (
          <button
            type="button"
            onClick={openCreate}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium"
            style={{ border: "1px solid var(--line)" }}
          >
            <Plus size={16} />
            New Template
          </button>
        )}
      </div>

      {templates.length === 0 ? (
        <EmptyState
          title="No templates yet"
          detail="Create a template to save prompts for reuse in the Compare tab."
        />
      ) : (
        <div className="surface-panel overflow-hidden">
          <table className="data-table w-full">
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Version</th>
                <th>Updated</th>
                {canManage && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {templates.map((t) => (
                <tr key={t.id}>
                  <td>
                    <button
                      type="button"
                      onClick={() => onSelectTemplate?.(t)}
                      className="text-left font-medium hover:underline"
                      style={{ color: "var(--accent-sky)" }}
                    >
                      {t.name}
                    </button>
                  </td>
                  <td style={{ color: "var(--muted)", maxWidth: 200 }}>
                    {t.description?.slice(0, 60) ?? "—"}
                    {t.description && t.description.length > 60 ? "…" : ""}
                  </td>
                  <td>v{t.version}</td>
                  <td style={{ color: "var(--muted)" }}>
                    {new Date(t.updated_at).toLocaleDateString()}
                  </td>
                  {canManage && (
                    <td>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => openEdit(t)}
                          className="p-1.5 rounded hover:bg-[rgba(0,0,0,0.06)]"
                          title="Edit"
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            if (window.confirm("Delete this template?")) {
                              deleteMutation.mutate(t.id);
                            }
                          }}
                          className="p-1.5 rounded hover:bg-[rgba(0,0,0,0.06)]"
                          style={{ color: "var(--accent-rose)" }}
                          title="Delete"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingId ? "Edit Template" : "New Template"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="stack-form">
            <label className="inline-control">
              Name
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))}
                placeholder="e.g. Customer support reply"
              />
            </label>
            <label className="inline-control">
              Description (optional)
              <input
                type="text"
                value={formData.description}
                onChange={(e) => setFormData((p) => ({ ...p, description: e.target.value }))}
                placeholder="Brief description"
              />
            </label>
            <label className="inline-control">
              System message (optional)
              <textarea
                value={formData.system_message}
                onChange={(e) => setFormData((p) => ({ ...p, system_message: e.target.value }))}
                rows={2}
                placeholder="You are a helpful assistant..."
              />
            </label>
            <label className="inline-control">
              User template
              <textarea
                value={formData.user_template}
                onChange={(e) => setFormData((p) => ({ ...p, user_template: e.target.value }))}
                rows={4}
                placeholder="Hello {{name}}, your order {{order_id}}..."
                className="font-mono text-sm"
              />
            </label>
            <DialogFooter>
              <button type="button" onClick={() => setShowModal(false)}>
                Cancel
              </button>
              <button
                type="submit"
                disabled={createMutation.isPending || updateMutation.isPending}
              >
                {editingId ? "Update" : "Create"}
              </button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function PlaygroundPage() {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState<TabId>("compare");
  const [loadedTemplate, setLoadedTemplate] = useState<PromptTemplate | null>(null);
  const clearTemplate = useCallback(() => setLoadedTemplate(null), []);

  const tabs: { id: TabId; label: string; icon: React.ElementType }[] = [
    { id: "compare", label: "Compare", icon: Beaker },
    { id: "templates", label: "Templates", icon: FileText },
  ];

  return (
    <section className="page-wrap">
      <header className="page-header">
        <p className="eyebrow">Prompt Playground</p>
        <h1>Model Comparison & Templates</h1>
      </header>

      <div className="flex gap-1 border-b mb-6" style={{ borderColor: "var(--line)" }}>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-t-lg text-sm font-medium transition-colors",
                activeTab === tab.id
                  ? "bg-[var(--accent-sky)] text-white"
                  : "hover:bg-[rgba(44,109,191,0.08)]"
              )}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {activeTab === "compare" && (
        <CompareTab
          token={token!}
          loadedTemplate={loadedTemplate}
          onClearTemplate={clearTemplate}
        />
      )}
      {activeTab === "templates" && (
        <TemplatesTab
          token={token!}
          onSelectTemplate={(t) => {
            setLoadedTemplate(t);
            setActiveTab("compare");
          }}
        />
      )}
    </section>
  );
}
