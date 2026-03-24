import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Users, Copy, Check, Mail } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type {
  TeamResponse,
  TeamDetailResponse,
  CreateTeamRequest,
  UserResponse,
  InviteCreatedResponse,
  InviteCreateRequest,
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

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }
  return (
    <button
      type="button"
      onClick={copy}
      title="Copy to clipboard"
      style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--accent-sky)", padding: "2px 4px" }}
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}

function ManageMembersModal({
  team,
  open,
  onClose,
  users,
  token,
  onAddMember,
  onRemoveMember,
}: {
  team: TeamDetailResponse | null;
  open: boolean;
  onClose: () => void;
  users: UserResponse[];
  token: string;
  onAddMember: (teamId: string, userId: string) => void;
  onRemoveMember: (teamId: string, userId: string) => void;
}) {
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"developer" | "admin" | "viewer">("developer");
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);

  const inviteMutation = useMutation({
    mutationFn: (req: InviteCreateRequest) =>
      apiClient.post<InviteCreatedResponse>("/api/v1/invites", req, token),
    onSuccess: (data) => {
      setInviteUrl(data.invite_url);
      setInviteEmail("");
      toast.success(`Invite sent to ${data.email}`);
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to send invite"),
  });

  if (!team) return null;
  const memberIds = new Set((team.members ?? []).map((m) => m.id));
  const nonMembers = users.filter((u) => !memberIds.has(u.id));

  function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    inviteMutation.mutate({ email: inviteEmail.trim(), role: inviteRole });
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) { onClose(); setInviteUrl(null); } }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Members — {team.name}</DialogTitle>
        </DialogHeader>

        <div className="stack-form">
          {/* Current members */}
          <div>
            <p style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>
              Current members ({team.members.length})
            </p>
            {team.members.length === 0 ? (
              <p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>No members yet — invite someone below.</p>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {team.members.map((m) => (
                  <li key={m.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0.4rem 0", borderBottom: "1px solid var(--line)" }}>
                    <span style={{ fontSize: "0.875rem" }}>
                      {m.email}
                      {m.name ? <span style={{ color: "var(--muted)", marginLeft: 4 }}>({m.name})</span> : null}
                    </span>
                    <button type="button" onClick={() => onRemoveMember(team.id, m.id)} style={{ border: "none", background: "transparent", color: "var(--accent-rose)", cursor: "pointer", fontSize: "0.8rem" }}>
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Add existing org user */}
          {nonMembers.length > 0 && (
            <div>
              <p style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>
                Add existing user
              </p>
              <select
                aria-label="Add existing member"
                style={{ padding: "0.5rem", width: "100%", borderRadius: "4px" }}
                onChange={(e) => {
                  const userId = e.target.value;
                  if (userId) { onAddMember(team.id, userId); e.target.value = ""; }
                }}
              >
                <option value="">Select a team member…</option>
                {nonMembers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.email}{u.name ? ` (${u.name})` : ""}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Invite by email */}
          <div style={{ borderTop: "1px solid var(--line)", paddingTop: "0.75rem" }}>
            <p style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>
              <Mail size={12} style={{ display: "inline", marginRight: 4 }} />
              Invite someone new
            </p>
            <p style={{ fontSize: "0.8rem", color: "var(--muted)", marginBottom: "0.75rem" }}>
              They'll receive an email with a link to create their account and join your org.
            </p>
            <form onSubmit={handleInvite} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="colleague@company.com"
                required
                style={{ padding: "0.5rem", borderRadius: "4px", border: "1px solid var(--line)" }}
              />
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as "developer" | "admin" | "viewer")}
                  style={{ padding: "0.5rem", borderRadius: "4px", border: "1px solid var(--line)", flex: 1 }}
                >
                  <option value="developer">Developer</option>
                  <option value="viewer">Viewer</option>
                  <option value="admin">Admin</option>
                </select>
                <button type="submit" disabled={inviteMutation.isPending} style={{ background: "var(--accent-sky)", whiteSpace: "nowrap" }}>
                  {inviteMutation.isPending ? "Sending…" : "Send Invite"}
                </button>
              </div>
            </form>

            {/* Invite link to copy */}
            {inviteUrl && (
              <div style={{ marginTop: "0.75rem", background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: "0.6rem 0.75rem" }}>
                <p style={{ fontSize: "0.75rem", color: "var(--muted)", marginBottom: "0.3rem", fontWeight: 600 }}>Invite link — share this directly</p>
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <code style={{ flex: 1, fontSize: "0.72rem", wordBreak: "break-all", color: "var(--accent-sky)" }}>{inviteUrl}</code>
                  <CopyButton text={inviteUrl} />
                </div>
              </div>
            )}
          </div>
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
        token={token!}
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
