import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type { ApiKeyCreatedResponse, ApiKeyResponse } from "../../api/types";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { LoadingState } from "../../components/LoadingState";
import { useAuth } from "../../state/AuthContext";

export function ApiKeysPage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const [newKeyName, setNewKeyName] = useState("sdk-default");
  const [latestCreatedKey, setLatestCreatedKey] = useState<ApiKeyCreatedResponse | null>(null);

  const keysQuery = useQuery({
    queryKey: ["api-keys", token],
    queryFn: () => apiClient.get<ApiKeyResponse[]>("/api/v1/api-keys", token!),
    enabled: Boolean(token),
  });

  const createMutation = useMutation({
    mutationFn: (name: string) =>
      apiClient.post<ApiKeyCreatedResponse>(
        "/api/v1/api-keys",
        { name, permissions: ["proxy:llm"], expires_at: null },
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
    await createMutation.mutateAsync(newKeyName);
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
            required
          />
          <button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Creating..." : "Create Key"}
          </button>
        </form>

        {latestCreatedKey ? (
          <section className="key-reveal" role="status" aria-live="polite">
            <p>Copy this key now. It will not be shown again.</p>
            <code>{latestCreatedKey.key}</code>
          </section>
        ) : null}
      </section>

      <section className="surface-panel">
        {keys.length === 0 ? (
          <EmptyState title="No API keys" detail="Create a key to authorize gateway traffic." />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
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




