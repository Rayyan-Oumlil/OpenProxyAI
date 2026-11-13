import { useId, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type {
  Space,
  SpaceCreate,
  SpaceUpdate,
  TeamChoice,
} from "../../api/conversationTypes";
import { useConfirm } from "../../components/ui/ConfirmDialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
import { friendlyError } from "../../lib/conversations";
import { useAuth } from "../../state/AuthContext";
import { SPACES, useSpaces } from "./SpacePicker";

const TEAMS = "/api/v1/conversations/teams";

function SpaceRow({
  space,
  onRename,
  onDelete,
  busy,
}: {
  space: Space;
  onRename: (name: string) => void;
  onDelete: () => void;
  busy: boolean;
}) {
  const nameId = useId();
  const [name, setName] = useState(space.name);
  const changed = name.trim() !== space.name && name.trim() !== "";
  const summary = `${space.team_id ? "Team space" : "Personal"} · ${space.conversation_count} ${space.conversation_count === 1 ? "conversation" : "conversations"}`;
  return (
    <li className="space-row">
      {space.is_owner ? (
        <>
          <label className="sr-only" htmlFor={nameId}>
            Name of space {space.name}
          </label>
          <input
            id={nameId}
            value={name}
            maxLength={100}
            onChange={(e) => setName(e.target.value)}
          />
          <button
            type="button"
            className="btn-outline"
            disabled={!changed || busy}
            onClick={() => onRename(name.trim())}
          >
            Rename
          </button>
          <button
            type="button"
            className="btn-outline"
            aria-label={`Delete space ${space.name}`}
            disabled={busy}
            onClick={onDelete}
          >
            <Trash2 size={14} aria-hidden="true" />
          </button>
        </>
      ) : (
        <strong>{space.name}</strong>
      )}
      <span className="text-muted text-sm">{summary}</span>
    </li>
  );
}

/** Create, rename and delete spaces. Deleting a space keeps its conversations; they just leave the folder. */
export function SpacesDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { token } = useAuth();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const ids = { name: useId(), team: useId() };
  const [name, setName] = useState("");
  const [teamId, setTeamId] = useState("");
  const spaces = useSpaces(open);
  const teams = useQuery({
    queryKey: ["conversation-teams"],
    queryFn: () => apiClient.get<TeamChoice[]>(TEAMS, token!),
    enabled: Boolean(token && open),
  });
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["spaces"] });
    void qc.invalidateQueries({ queryKey: ["conversations"] });
    void qc.invalidateQueries({ queryKey: ["conversation"] });
  };
  const fail = (fallback: string) => (e: unknown) =>
    toast.error(friendlyError(e instanceof Error ? e.message : fallback));

  const create = useMutation({
    mutationFn: (body: SpaceCreate) =>
      apiClient.post<Space>(SPACES, body, token!),
    onSuccess: () => {
      setName("");
      setTeamId("");
      refresh();
    },
    onError: fail("Could not create the space."),
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: SpaceUpdate }) =>
      apiClient.patch<Space>(`${SPACES}/${id}`, body, token!),
    onSuccess: refresh,
    onError: fail("Could not rename the space."),
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiClient.del<void>(`${SPACES}/${id}`, token!),
    onSuccess: refresh,
    onError: fail("Could not delete the space."),
  });
  const busy = create.isPending || update.isPending || remove.isPending;

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Spaces</DialogTitle>
          <DialogDescription>
            A space is a folder for finding conversations. Putting a
            conversation in one does not share it: people see only the
            conversations they could already read.
          </DialogDescription>
        </DialogHeader>
        {spaces.isError ? <p role="alert">Could not load spaces.</p> : null}
        {spaces.isSuccess && spaces.data.length === 0 ? (
          <p className="text-muted text-sm">No spaces yet.</p>
        ) : null}
        <ul className="space-list" aria-label="Your spaces">
          {(spaces.data ?? []).map((s) => (
            <SpaceRow
              key={s.id}
              space={s}
              busy={busy}
              onRename={(n) => update.mutate({ id: s.id, body: { name: n } })}
              onDelete={async () => {
                if (
                  await confirm({
                    title: `Delete the space "${s.name}"?`,
                    description:
                      "Its conversations are not deleted; they just leave the space.",
                    confirmLabel: "Delete space",
                    destructive: true,
                  })
                )
                  remove.mutate(s.id);
              }}
            />
          ))}
        </ul>
        <form
          className="stack-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (!name.trim()) return toast.error("Give the space a name.");
            create.mutate({
              name: name.trim(),
              ...(teamId ? { team_id: teamId } : {}),
            });
          }}
        >
          <label className="inline-control" htmlFor={ids.name}>
            New space
            <input
              id={ids.name}
              value={name}
              maxLength={100}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Q3 planning"
            />
          </label>
          <label className="inline-control" htmlFor={ids.team}>
            Visible to
            <select
              id={ids.team}
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
            >
              <option value="">Only me</option>
              {(teams.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  Team: {t.name}
                </option>
              ))}
            </select>
          </label>
          <DialogFooter>
            <button type="button" className="btn-outline" onClick={onClose}>
              Close
            </button>
            <button type="submit" disabled={busy} className="bg-accent-sky">
              Create space
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
