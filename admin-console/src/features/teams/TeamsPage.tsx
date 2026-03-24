import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Users } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type {
  TeamResponse,
  TeamDetailResponse,
  CreateTeamRequest,
  UserResponse,
} from "../../api/types";
import { LoadingState } from "../../components/LoadingState";
import { ErrorState } from "../../components/ErrorState";
import { EmptyState } from "../../components/EmptyState";
import { formatDate } from "../../lib/utils";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "../../components/ui/dialog";
import { useAuth } from "../../state/AuthContext";

function AddTeamModal({
  open,
  onClose,
  onSave,
  isSaving,
}: {
  open: boolean;
  onClose: () => void;
  onSave: (data: CreateTeamRequest) => void;
  isSaving: boolean;
}) {
  const [name, setName] = useState("");
  const [budget, setBudget] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      toast.error("Team name is required.");
      return;
    }
    const budgetNum = budget ? parseFloat(budget) : null;
    if (budgetNum !== null && (isNaN(budgetNum) || budgetNum < 0)) {
      toast.error("Budget must be a non-negative number.");
      return;
    }
    onSave({
      name: name.trim(),
      budget_monthly_usd: budgetNum,
    });
    setName("");
    setBudget("");
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Team</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="stack-form">
          <label className="inline-control">
            Name
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Engineering"
              required
            />
          </label>
          <label className="inline-control">
            Monthly Budget (USD)
            <input
              type="number"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              placeholder="Optional"
              min="0"
              step="0.01"
            />
          </label>
          <DialogFooter>
            <button
              type="button"
              onClick={onClose}
              style={{
                background: "transparent",
                color: "var(--muted)",
                border: "1px solid var(--line)",
              }}
            >
              Cancel
            </button>
            <button type="submit" disabled={isSaving} style={{ background: "var(--accent-sky)" }}>
              {isSaving ? "Creating…" : "Create Team"}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ManageMembersModal({
  team,
  open,
  onClose,
  users,
  onAddMember,
  onRemoveMember,
}: {
  team: TeamDetailResponse | null;
  open: boolean;
  onClose: () => void;
  users: UserResponse[];
  onAddMember: (teamId: string, userId: string) => void;
  onRemoveMember: (teamId: string, userId: string) => void;
}) {
  if (!team) return null;
  const memberIds = new Set((team.members ?? []).map((m) => m.id));
  const nonMembers = users.filter((u) => !memberIds.has(u.id));

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Manage Members — {team.name}</DialogTitle>
        </DialogHeader>
        <div className="stack-form">
          <div>
            <p style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "0.5rem" }}>
              Current members ({team.members.length})
            </p>
            {team.members.length === 0 ? (
              <p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>No members yet.</p>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {team.members.map((m) => (
                  <li
                    key={m.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "0.5rem 0",
                      borderBottom: "1px solid var(--line)",
                    }}
                  >
                    <span>
                      {m.email}
                      {m.name ? ` (${m.name})` : ""}
                    </span>
                    <button
                      type="button"
                      onClick={() => onRemoveMember(team.id, m.id)}
                      style={{
                        border: "none",
                        background: "transparent",
                        color: "var(--accent-rose)",
                        cursor: "pointer",
                        fontSize: "0.8rem",
                      }}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {nonMembers.length > 0 && (
            <div>
              <p style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "0.5rem" }}>
                Add member
              </p>
              <select
                aria-label="Add member"
                style={{ padding: "0.5rem", width: "100%", borderRadius: "4px" }}
                onChange={(e) => {
                  const userId = e.target.value;
                  if (userId) {
                    onAddMember(team.id, userId);
                    e.target.value = "";
                  }
                }}
              >
                <option value="">Select user…</option>
                {nonMembers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.email} {u.name ? `(${u.name})` : ""}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function TeamsPage() {
  const { token, user } = useAuth();
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [manageTeamId, setManageTeamId] = useState<string | null>(null);

  const teamsQuery = useQuery({
    queryKey: ["teams", token],
    queryFn: () => apiClient.get<TeamResponse[]>("/api/v1/teams", token!),
    enabled: Boolean(token),
  });

  const teamDetailQuery = useQuery({
    queryKey: ["team", manageTeamId, token],
    queryFn: () =>
      apiClient.get<TeamDetailResponse>(`/api/v1/teams/${manageTeamId}`, token!),
    enabled: Boolean(token && manageTeamId),
  });

  const usersQuery = useQuery({
    queryKey: ["users", token],
    queryFn: () => apiClient.get<UserResponse[]>("/api/v1/users", token!),
    enabled: Boolean(token),
  });

  const addMutation = useMutation({
    mutationFn: (data: CreateTeamRequest) =>
      apiClient.post<TeamResponse>("/api/v1/teams", data, token!),
    onSuccess: () => {
      toast.success("Team created.");
      qc.invalidateQueries({ queryKey: ["teams"] });
      setShowAdd(false);
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to create team"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.del(`/api/v1/teams/${id}`, token!),
    onSuccess: () => {
      toast.success("Team deleted.");
      qc.invalidateQueries({ queryKey: ["teams"] });
      setManageTeamId(null);
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to delete team"),
  });

  const addMemberMutation = useMutation({
    mutationFn: ({ teamId, userId }: { teamId: string; userId: string }) =>
      apiClient.post(`/api/v1/teams/${teamId}/members/${userId}`, {}, token!),
    onSuccess: () => {
      toast.success("Member added.");
      if (manageTeamId) qc.invalidateQueries({ queryKey: ["team", manageTeamId] });
      qc.invalidateQueries({ queryKey: ["teams"] });
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to add member"),
  });

  const removeMemberMutation = useMutation({
    mutationFn: ({ teamId, userId }: { teamId: string; userId: string }) =>
      apiClient.del(`/api/v1/teams/${teamId}/members/${userId}`, token!),
    onSuccess: () => {
      toast.success("Member removed.");
      if (manageTeamId) qc.invalidateQueries({ queryKey: ["team", manageTeamId] });
      qc.invalidateQueries({ queryKey: ["teams"] });
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to remove member"),
  });

  const canManage = user?.role === "admin";

  function handleDelete(id: string) {
    if (!window.confirm("Delete this team? Members will be unassigned.")) return;
    deleteMutation.mutate(id);
  }

  if (teamsQuery.isLoading) return <LoadingState label="Loading teams…" />;
  if (teamsQuery.isError)
    return (
      <ErrorState
        title="Unable to load teams"
        detail={
          teamsQuery.error instanceof Error ? teamsQuery.error.message : "Unknown error"
        }
      />
    );

  const teams = teamsQuery.data ?? [];

  return (
    <section className="page-wrap">
      <header className="page-header with-controls">
        <div>
          <p className="eyebrow">Cost Attribution</p>
          <h1>Teams</h1>
        </div>
        {canManage && (
          <button
            type="button"
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5"
            style={{ background: "var(--accent-sky)" }}
          >
            <Plus size={15} />
            Create Team
          </button>
        )}
      </header>

      {!canManage ? (
        <EmptyState
          title="Admin only"
          detail="Only admins can create and manage teams."
        />
      ) : teams.length === 0 ? (
        <EmptyState
          title="No teams"
          detail="Create teams to attribute costs by department or project."
        />
      ) : (
        <section className="surface-panel">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Monthly Budget</th>
                <th>Members</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {teams.map((t) => (
                <tr key={t.id}>
                  <td>{t.name}</td>
                  <td>
                    {t.budget_monthly_usd != null
                      ? `$${parseFloat(t.budget_monthly_usd).toFixed(2)}`
                      : "—"}
                  </td>
                  <td>{t.member_count}</td>
                  <td style={{ color: "var(--muted)", fontSize: "0.82rem" }}>
                    {formatDate(t.created_at)}
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        title="Manage members"
                        onClick={() => setManageTeamId(t.id)}
                        style={{
                          border: "none",
                          background: "transparent",
                          padding: "2px",
                          cursor: "pointer",
                        }}
                      >
                        <Users size={18} style={{ color: "var(--accent-sky)" }} />
                      </button>
                      <button
                        type="button"
                        title="Delete"
                        onClick={() => handleDelete(t.id)}
                        style={{
                          border: "none",
                          background: "transparent",
                          padding: "2px",
                          cursor: "pointer",
                        }}
                      >
                        <Trash2 size={14} style={{ color: "var(--accent-rose)" }} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <AddTeamModal
        open={showAdd}
        onClose={() => setShowAdd(false)}
        onSave={(data) => addMutation.mutate(data)}
        isSaving={addMutation.isPending}
      />

      <ManageMembersModal
        team={teamDetailQuery.data ?? null}
        open={Boolean(manageTeamId)}
        onClose={() => setManageTeamId(null)}
        users={usersQuery.data ?? []}
        onAddMember={(teamId, userId) =>
          addMemberMutation.mutate({ teamId, userId })
        }
        onRemoveMember={(teamId, userId) =>
          removeMemberMutation.mutate({ teamId, userId })
        }
      />
    </section>
  );
}
