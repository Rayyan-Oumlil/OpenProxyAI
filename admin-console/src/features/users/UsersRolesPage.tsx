import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type { UserResponse } from "../../api/types";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { LoadingState } from "../../components/LoadingState";
import { useAuth } from "../../state/AuthContext";

export function UsersRolesPage() {
  const { token, user } = useAuth();
  const queryClient = useQueryClient();

  const usersQuery = useQuery({
    queryKey: ["users", token],
    queryFn: () => apiClient.get<UserResponse[]>("/api/v1/users", token!),
    enabled: Boolean(token),
  });

  const updateUserMutation = useMutation({
    mutationFn: ({ userId, payload }: { userId: string; payload: Record<string, unknown> }) =>
      apiClient.patch<UserResponse>(`/api/v1/users/${userId}`, payload, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users", token] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Failed to update user");
      queryClient.invalidateQueries({ queryKey: ["users", token] });
    },
  });

  const canManageUsers = user?.role === "admin";

  if (usersQuery.isLoading) {
    return <LoadingState label="Loading users..." />;
  }

  if (usersQuery.isError) {
    return (
      <ErrorState
        title="Unable to load users"
        detail={usersQuery.error instanceof Error ? usersQuery.error.message : "Unknown error"}
      />
    );
  }

  const users = usersQuery.data ?? [];

  return (
    <section className="page-wrap">
      <header className="page-header">
        <p className="eyebrow">Team Access</p>
        <h1>Users &amp; Roles</h1>
      </header>

      {!canManageUsers ? (
        <EmptyState
          title="Read-only access"
          detail="Only admin users can modify roles and activation status."
        />
      ) : null}

      <section className="surface-panel">
        {users.length === 0 ? (
          <EmptyState title="No users in organization" detail="Invite users from onboarding or auth flows." />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Name</th>
                <th>Role</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((row) => {
                const isSelf = row.id === user?.id;
                return (
                <tr key={row.id}>
                  <td>{row.email}</td>
                  <td>{row.name ?? "-"}</td>
                  <td>
                    {canManageUsers && !isSelf ? (
                      <select
                        value={row.role}
                        onChange={(event) => {
                          updateUserMutation.mutate({
                            userId: row.id,
                            payload: { role: event.target.value },
                          });
                        }}
                        disabled={updateUserMutation.isPending}
                      >
                        <option value="admin">admin</option>
                        <option value="developer">developer</option>
                        <option value="viewer">viewer</option>
                      </select>
                    ) : (
                      <span>{row.role}{isSelf && <span className="text-muted text-xs ml-1">(you)</span>}</span>
                    )}
                  </td>
                  <td>{row.is_active ? "active" : "inactive"}</td>
                  <td>{new Date(row.created_at).toLocaleDateString()}</td>
                  <td>
                    <button
                      type="button"
                      disabled={!canManageUsers || isSelf || updateUserMutation.isPending}
                      onClick={() => {
                        updateUserMutation.mutate({
                          userId: row.id,
                          payload: { is_active: !row.is_active },
                        });
                      }}
                    >
                      {row.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </section>
  );
}

