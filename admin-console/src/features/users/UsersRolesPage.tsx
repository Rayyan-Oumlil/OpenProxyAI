import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type { UserResponse } from "../../api/types";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { useAuth } from "../../state/AuthContext";
import { formatDate } from "../../lib/utils";

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

  const columns: Column<UserResponse>[] = [
    { key: "email", header: "Email", cell: (row) => row.email },
    { key: "name", header: "Name", cell: (row) => row.name ?? "-" },
    {
      key: "role",
      header: "Role",
      cell: (row) => {
        const isSelf = row.id === user?.id;
        if (canManageUsers && !isSelf) {
          return (
            <select
              aria-label={`Role for ${row.email}`}
              value={row.role}
              onChange={(event) => updateUserMutation.mutate({ userId: row.id, payload: { role: event.target.value } })}
              disabled={updateUserMutation.isPending}
            >
              <option value="admin">admin</option>
              <option value="developer">developer</option>
              <option value="viewer">viewer</option>
            </select>
          );
        }
        return (
          <span>
            {row.role}
            {isSelf ? <span className="text-muted text-xs ml-1">(you)</span> : null}
          </span>
        );
      },
    },
    {
      key: "status",
      header: "Status",
      cell: (row) => <StatusBadge verdict={row.is_active ? "allowed" : "neutral"}>{row.is_active ? "Active" : "Inactive"}</StatusBadge>,
    },
    { key: "created", header: "Created", nowrap: true, cell: (row) => formatDate(row.created_at) },
    {
      key: "actions",
      header: "Actions",
      cell: (row) => (
        <button
          type="button"
          aria-label={`${row.is_active ? "Deactivate" : "Activate"} ${row.email}`}
          disabled={!canManageUsers || row.id === user?.id || updateUserMutation.isPending}
          onClick={() => updateUserMutation.mutate({ userId: row.id, payload: { is_active: !row.is_active } })}
        >
          {row.is_active ? "Deactivate" : "Activate"}
        </button>
      ),
    },
  ];

  return (
    <section className="page-wrap">
      <PageHeader title="Users & roles" description="Who can sign in to this organization, and what they can do." />

      {!canManageUsers ? (
        <p className="trace-note" role="status">
          Read-only access. Only admin users can modify roles and activation status.
        </p>
      ) : null}

      <DataTable
        caption="Users"
        columns={columns}
        rows={usersQuery.data}
        getRowId={(row) => row.id}
        isLoading={usersQuery.isLoading}
        error={
          usersQuery.isError
            ? {
                title: "Unable to load users",
                detail: usersQuery.error instanceof Error ? usersQuery.error.message : "Unknown error",
                onRetry: () => void usersQuery.refetch(),
              }
            : null
        }
        empty={{ title: "No users in organization", detail: "Invite users from onboarding or auth flows." }}
      />
    </section>
  );
}
