import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Copy, Check } from "lucide-react";

import { apiClient } from "../../api/client";
import type { ApiKeyCreatedResponse, ApiKeyResponse } from "../../api/types";
import type { TeamResponse } from "../../api/types";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { LoadingState } from "../../components/LoadingState";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "../../components/ui/dialog";
import { useAuth } from "../../state/AuthContext";

const BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  "https://openproxyai-backend-ikcideatha-nn.a.run.app";

type Lang = "curl" | "python" | "typescript";

const LANG_LABELS: { id: Lang; label: string }[] = [
  { id: "curl", label: "cURL" },
  { id: "python", label: "Python" },
  { id: "typescript", label: "TypeScript" },
];

function buildSnippet(lang: Lang, key: string): string {
  switch (lang) {
    case "curl":
      return `curl ${BASE_URL}/v1/chat/completions \\
  -H "Authorization: Bearer ${key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "anthropic/claude-haiku-4-5-20251001",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'`;
    case "python":
      return `from openai import OpenAI

client = OpenAI(
    api_key="${key}",
    base_url="${BASE_URL}/v1",
)

response = client.chat.completions.create(
    model="anthropic/claude-haiku-4-5-20251001",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)`;
    case "typescript":
      return `import OpenAI from "openai";

const client = new OpenAI({
  apiKey: "${key}",
  baseURL: "${BASE_URL}/v1",
});

const response = await client.chat.completions.create({
  model: "anthropic/claude-haiku-4-5-20251001",
  messages: [{ role: "user", content: "Hello!" }],
});
console.log(response.choices[0].message.content);`;
  }
}

function KeyCreatedModal({
  created,
  onClose,
}: {
  created: ApiKeyCreatedResponse;
  onClose: () => void;
}) {
  const [lang, setLang] = useState<Lang>("curl");
  const [keyCopied, setKeyCopied] = useState(false);
  const [snippetCopied, setSnippetCopied] = useState(false);

  function copyKey() {
    navigator.clipboard.writeText(created.key);
    setKeyCopied(true);
    setTimeout(() => setKeyCopied(false), 2000);
  }

  function copySnippet() {
    navigator.clipboard.writeText(buildSnippet(lang, created.key));
    setSnippetCopied(true);
    setTimeout(() => setSnippetCopied(false), 2000);
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>API Key Created</DialogTitle>
        </DialogHeader>

        {/* Key reveal */}
        <div
          style={{
            background: "var(--bg)",
            border: "1px solid var(--line)",
            borderRadius: 10,
            padding: "0.75rem 1rem",
          }}
        >
          <p style={{ fontSize: "0.75rem", color: "var(--muted)", marginBottom: "0.4rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Your key — copy it now, it won't be shown again
          </p>
          <div className="flex items-center gap-2">
            <code style={{ flex: 1, fontSize: "0.8rem", wordBreak: "break-all" }}>{created.key}</code>
            <button
              type="button"
              onClick={copyKey}
              title="Copy key"
              style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--accent-sky)", padding: "0.25rem", flexShrink: 0 }}
            >
              {keyCopied ? <Check size={15} /> : <Copy size={15} />}
            </button>
          </div>
        </div>

        {/* Test snippets */}
        <div style={{ marginTop: "1rem" }}>
          <p style={{ fontSize: "0.82rem", fontWeight: 600, marginBottom: "0.5rem" }}>Test it now</p>
          <div className="flex gap-1 mb-2" role="tablist">
            {LANG_LABELS.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={lang === id}
                onClick={() => { setLang(id); setSnippetCopied(false); }}
                style={{
                  padding: "0.25rem 0.75rem",
                  borderRadius: 6,
                  fontSize: "0.8rem",
                  border: "1px solid var(--line)",
                  cursor: "pointer",
                  background: lang === id ? "var(--accent-sky)" : "transparent",
                  color: lang === id ? "#fff" : "var(--muted)",
                  fontWeight: lang === id ? 600 : 400,
                }}
              >
                {label}
              </button>
            ))}
          </div>

          <div style={{ position: "relative" }}>
            <pre
              style={{
                background: "var(--bg)",
                border: "1px solid var(--line)",
                borderRadius: 10,
                padding: "0.75rem 1rem",
                fontSize: "0.75rem",
                overflow: "auto",
                maxHeight: 220,
                fontFamily: "JetBrains Mono, Fira Code, monospace",
                whiteSpace: "pre",
                margin: 0,
              }}
            >
              {buildSnippet(lang, created.key)}
            </pre>
            <button
              type="button"
              onClick={copySnippet}
              title="Copy snippet"
              style={{
                position: "absolute",
                top: 8,
                right: 8,
                background: "var(--surface)",
                border: "1px solid var(--line)",
                borderRadius: 6,
                cursor: "pointer",
                padding: "0.25rem 0.5rem",
                color: "var(--accent-sky)",
                fontSize: "0.75rem",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              {snippetCopied ? <Check size={12} /> : <Copy size={12} />}
              {snippetCopied ? "Copied" : "Copy"}
            </button>
          </div>
        </div>

        <DialogFooter>
          <button type="button" onClick={onClose} className="bg-accent-sky">
            Done
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ApiKeysPage() {
  const { token, user } = useAuth();
  const queryClient = useQueryClient();
  const [newKeyName, setNewKeyName] = useState("");
  const [selectedTeamId, setSelectedTeamId] = useState<string>("");
  const [latestCreatedKey, setLatestCreatedKey] = useState<ApiKeyCreatedResponse | null>(null);

  const keysQuery = useQuery({
    queryKey: ["api-keys", token],
    queryFn: () => apiClient.get<ApiKeyResponse[]>("/api/v1/api-keys", token!),
    enabled: Boolean(token),
  });

  const teamsQuery = useQuery({
    queryKey: ["teams", token],
    queryFn: () => apiClient.get<TeamResponse[]>("/api/v1/teams", token!),
    enabled: Boolean(token) && user?.role === "admin",
  });

  const createMutation = useMutation({
    mutationFn: ({ name, teamId }: { name: string; teamId: string | null }) =>
      apiClient.post<ApiKeyCreatedResponse>(
        "/api/v1/api-keys",
        {
          name,
          permissions: ["proxy:llm"],
          expires_at: null,
          team_id: teamId || null,
        },
        token ?? undefined
      ),
    onSuccess: (created) => {
      setLatestCreatedKey(created);
      queryClient.invalidateQueries({ queryKey: ["api-keys", token] });
      toast.success("API key created.");
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed to create API key.");
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => apiClient.del<void>(`/api/v1/api-keys/${id}`, token ?? undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys", token] });
      toast.success("Key revoked.");
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed to revoke key.");
    },
  });

  const onCreateKey = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await createMutation.mutateAsync({
      name: newKeyName,
      teamId: selectedTeamId || null,
    });
    setNewKeyName("");
  };

  if (keysQuery.isLoading) {
    return <LoadingState label="Loading API keys..." />;
  }

  if (keysQuery.isError) {
    return (
      <ErrorState
        title="Unable to load API keys"
        detail={keysQuery.error instanceof Error ? keysQuery.error.message : "Unknown error"}
      />
    );
  }

  const keys = keysQuery.data ?? [];
  const teamById = new Map(
    (teamsQuery.data ?? []).map((t) => [t.id, t.name])
  );

  return (
    <section className="page-wrap">
      <header className="page-header">
        <p className="eyebrow">Access Control</p>
        <h1>API Keys</h1>
      </header>

      <section className="surface-panel">
        <form onSubmit={onCreateKey} className="inline-form">
          <label htmlFor="key-name">Key Name</label>
          <input
            id="key-name"
            name="key-name"
            type="text"
            value={newKeyName}
            onChange={(event) => setNewKeyName(event.target.value)}
            placeholder="e.g. my-app-key"
            required
          />
          {teamsQuery.data && teamsQuery.data.length > 0 && (
            <>
              <label htmlFor="key-team">Team (optional)</label>
              <select
                id="key-team"
                value={selectedTeamId}
                onChange={(e) => setSelectedTeamId(e.target.value)}
                style={{ border: "1px solid var(--line)", padding: "0.5rem" }}
              >
                <option value="">No team</option>
                {teamsQuery.data.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </>
          )}
          <button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Creating..." : "Create Key"}
          </button>
        </form>

        {latestCreatedKey && (
          <KeyCreatedModal
            created={latestCreatedKey}
            onClose={() => setLatestCreatedKey(null)}
          />
        )}
      </section>

      <section className="surface-panel">
        {keys.length === 0 ? (
          <EmptyState title="No API keys" detail="Create a key to authorize gateway traffic." />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Team</th>
                <th>Prefix</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id}>
                  <td>{key.name ?? "Unnamed"}</td>
                  <td>{key.team_id ? teamById.get(key.team_id) ?? key.team_id : "—"}</td>
                  <td>{key.key_prefix}</td>
                  <td>{key.is_active ? "active" : "revoked"}</td>
                  <td>{new Date(key.created_at).toLocaleString()}</td>
                  <td>
                    <button
                      type="button"
                      disabled={!key.is_active || revokeMutation.isPending}
                      onClick={() => revokeMutation.mutate(key.id)}
                    >
                      Revoke
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </section>
  );
}




