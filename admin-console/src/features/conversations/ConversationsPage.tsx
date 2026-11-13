import { useDeferredValue, useId, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Folder, Plus } from "lucide-react";
import { NavLink, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type {
  Conversation,
  ConversationCreate,
  ConversationScope,
  TeamChoice,
} from "../../api/conversationTypes";
import { Badge } from "../../components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
import { PageHeader } from "../../components/ui/PageHeader";
import { friendlyError } from "../../lib/conversations";
import { composeTags } from "../../lib/tags";
import { formatDate } from "../../lib/utils";
import { useAuth } from "../../state/AuthContext";
import { SpacePicker, useSpaces } from "./SpacePicker";
import { SpacesDialog } from "./SpacesDialog";
import { ThreadView } from "./ThreadView";

const CONVERSATIONS = "/api/v1/conversations";

function NewConversationDialog({
  open,
  onClose,
  onCreate,
  busy,
}: {
  open: boolean;
  onClose: () => void;
  onCreate: (body: ConversationCreate) => void;
  busy: boolean;
}) {
  const { token } = useAuth();
  const ids = {
    title: useId(),
    tags: useId(),
    team: useId(),
    persona: useId(),
    org: useId(),
    space: useId(),
    priv: useId(),
  };
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [teamId, setTeamId] = useState("");
  const [persona, setPersona] = useState("");
  const [wholeOrg, setWholeOrg] = useState(false);
  const [spaceId, setSpaceId] = useState("");
  const [keepPrivate, setKeepPrivate] = useState(false);
  const isAdmin = useAuth().user?.role === "admin";
  const teams = useQuery({
    queryKey: ["conversation-teams"],
    queryFn: () =>
      apiClient.get<TeamChoice[]>(`${CONVERSATIONS}/teams`, token!),
    enabled: Boolean(token && open),
  });

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New conversation</DialogTitle>
          <DialogDescription>
            Private to you unless you share it with a team you belong to. You
            can switch models in the middle of it.
          </DialogDescription>
        </DialogHeader>
        <form
          className="stack-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (!title.trim())
              return toast.error("Give the conversation a title.");
            onCreate({
              title: title.trim(),
              tags: composeTags(tags, keepPrivate),
              ...(persona.trim() ? { system_prompt: persona.trim() } : {}),
              ...(spaceId ? { space_id: spaceId } : {}),
              ...(keepPrivate
                ? {}
                : wholeOrg
                  ? { visibility: "org" as const }
                  : teamId
                    ? { visibility: "team" as const, team_id: teamId }
                    : {}),
            });
          }}
        >
          <label className="inline-control" htmlFor={ids.title}>
            Title
            <input
              id={ids.title}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
            />
          </label>
          <label className="inline-control" htmlFor={ids.tags}>
            Tags (optional, comma separated)
            <input
              id={ids.tags}
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="e.g. finance, q3"
            />
          </label>
          <label className="inline-control" htmlFor={ids.team}>
            Share with
            <select
              id={ids.team}
              value={teamId}
              disabled={wholeOrg || keepPrivate}
              onChange={(e) => setTeamId(e.target.value)}
            >
              <option value="">Nobody (private)</option>
              {(teams.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  Team: {t.name}
                </option>
              ))}
            </select>
          </label>
          {isAdmin ? (
            <label
              className="flex items-center gap-2 text-sm"
              htmlFor={ids.org}
            >
              <input
                id={ids.org}
                type="checkbox"
                checked={wholeOrg}
                disabled={keepPrivate}
                onChange={(e) => setWholeOrg(e.target.checked)}
              />
              Share with the whole organization (read-only for everyone else)
            </label>
          ) : null}
          <label className="flex items-center gap-2 text-sm" htmlFor={ids.priv}>
            <input
              id={ids.priv}
              type="checkbox"
              checked={keepPrivate}
              onChange={(e) => setKeepPrivate(e.target.checked)}
            />
            Keep private (it can then never be shared)
          </label>
          <SpacePicker id={ids.space} value={spaceId} onChange={setSpaceId} />
          <label className="inline-control" htmlFor={ids.persona}>
            Standing instruction (optional)
            <textarea
              id={ids.persona}
              className="textarea-short"
              value={persona}
              maxLength={4000}
              onChange={(e) => setPersona(e.target.value)}
              placeholder="e.g. You are a terse code reviewer."
            />
          </label>
          <DialogFooter>
            <button type="button" className="btn-outline" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" disabled={busy} className="bg-accent-sky">
              Start conversation
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function TagChips({ tags }: { tags: string[] }) {
  if (tags.length === 0) return null;
  return (
    <span className="conv__chips">
      {tags.map((t) => (
        <Badge key={t} variant="default">
          {t}
        </Badge>
      ))}
    </span>
  );
}

const SCOPES: {
  value: ConversationScope;
  label: string;
  adminOnly?: boolean;
}[] = [
  { value: "mine", label: "Mine" },
  { value: "shared", label: "Shared with me" },
  { value: "org", label: "Whole organization", adminOnly: true },
];

export function ConversationsPage() {
  const { token, user } = useAuth();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const isAdmin = user?.role === "admin";
  const [scope, setScope] = useState<ConversationScope>("mine");
  const [creating, setCreating] = useState(false);
  const [managingSpaces, setManagingSpaces] = useState(false);
  const [search, setSearch] = useState("");
  const [tag, setTag] = useState("");
  const [spaceFilter, setSpaceFilter] = useState("");
  const searchId = useId();
  const spaceFilterId = useId();
  const term = useDeferredValue(search.trim());
  const filtered = Boolean(term || tag || spaceFilter);
  const spaces = useSpaces();

  const params = new URLSearchParams({ scope });
  if (term) params.set("q", term);
  if (tag) params.set("tag", tag);
  if (spaceFilter) params.set("space_id", spaceFilter);
  const list = useQuery({
    queryKey: ["conversations", scope, term, tag, spaceFilter],
    queryFn: () =>
      apiClient.get<Conversation[]>(`${CONVERSATIONS}?${params}`, token!),
    enabled: Boolean(token),
  });
  // The tags to offer come from the unfiltered list, so choosing one does not make the others vanish.
  const everything = useQuery({
    queryKey: ["conversations", scope, "", "", ""],
    queryFn: () =>
      apiClient.get<Conversation[]>(`${CONVERSATIONS}?scope=${scope}`, token!),
    enabled: Boolean(token) && filtered,
  });
  const tagOptions = [
    ...new Set(
      (filtered ? everything.data : list.data)?.flatMap((c) => c.tags) ?? [],
    ),
  ].sort();

  const create = useMutation({
    mutationFn: (body: ConversationCreate) =>
      apiClient.post<Conversation>(CONVERSATIONS, body, token!),
    onSuccess: (created) => {
      setCreating(false);
      setScope("mine");
      setSearch("");
      setTag("");
      setSpaceFilter("");
      void qc.invalidateQueries({ queryKey: ["conversations"] });
      navigate(`/conversations/${created.id}`);
    },
    onError: (e) =>
      toast.error(
        friendlyError(
          e instanceof Error ? e.message : "Could not start the conversation.",
        ),
      ),
  });

  const rows = list.data ?? [];
  const metadataOnly = scope === "org";

  return (
    <div className="page">
      <PageHeader
        title="Conversations"
        description="Keep a conversation in the gateway and switch models as you go. Each model is sent only the earlier messages it is cleared for, and you are told what was held back."
        actions={
          <button
            type="button"
            className="bg-accent-sky"
            onClick={() => setCreating(true)}
          >
            <Plus size={14} aria-hidden="true" /> New conversation
          </button>
        }
      />
      <div className="conv">
        <nav className="conv__list" aria-label="Conversations">
          <div className="conv__scopes" role="group" aria-label="Show">
            {SCOPES.filter((s) => !s.adminOnly || isAdmin).map((s) => (
              <button
                key={s.value}
                type="button"
                className={
                  scope === s.value
                    ? "conv__scope conv__scope--on"
                    : "conv__scope"
                }
                aria-pressed={scope === s.value}
                onClick={() => setScope(s.value)}
              >
                {s.label}
              </button>
            ))}
          </div>
          <div className="conv__filters">
            <label className="sr-only" htmlFor={searchId}>
              Search titles and tags
            </label>
            <input
              id={searchId}
              type="search"
              value={search}
              maxLength={100}
              placeholder="Search titles and tags"
              onChange={(e) => setSearch(e.target.value)}
            />
            {(spaces.data ?? []).length > 0 ? (
              <SpacePicker
                id={spaceFilterId}
                label="Space"
                emptyLabel="All spaces"
                value={spaceFilter}
                onChange={setSpaceFilter}
              />
            ) : null}
            <button
              type="button"
              className="btn-outline"
              onClick={() => setManagingSpaces(true)}
            >
              <Folder size={14} aria-hidden="true" /> Spaces
            </button>
            {tagOptions.length > 0 ? (
              <div
                role="group"
                aria-label="Filter by tag"
                className="conv__tags"
              >
                {tagOptions.map((t) => (
                  <button
                    key={t}
                    type="button"
                    className={
                      tag === t ? "conv__scope conv__scope--on" : "conv__scope"
                    }
                    aria-pressed={tag === t}
                    onClick={() => setTag(tag === t ? "" : t)}
                  >
                    {t}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          {list.isError ? (
            <p role="alert">
              {list.error instanceof Error
                ? list.error.message
                : "Could not load conversations."}
            </p>
          ) : null}
          {list.isSuccess && rows.length === 0 ? (
            <p className="text-muted text-sm">
              {filtered
                ? "No conversation matches."
                : scope === "mine"
                  ? "No conversations yet. Start one."
                  : "Nothing here."}
            </p>
          ) : null}
          <ul>
            {rows.map((c) => (
              <li key={c.id}>
                {metadataOnly ? (
                  <div className="conv__item">
                    <strong>{c.title}</strong>
                    <span className="text-muted text-sm">
                      {c.owner_email} · {c.turn_count} messages ·{" "}
                      {formatDate(c.updated_at)}
                      {c.space_name ? ` · ${c.space_name}` : ""}
                    </span>
                    <TagChips tags={c.tags} />
                  </div>
                ) : (
                  <NavLink
                    to={`/conversations/${c.id}`}
                    className={({ isActive }) =>
                      isActive ? "conv__item conv__item--on" : "conv__item"
                    }
                  >
                    <strong>{c.title}</strong>
                    <span className="text-muted text-sm">
                      {c.turn_count} messages · {formatDate(c.updated_at)}
                      {c.visibility === "team" ? " · team" : ""}
                      {c.space_name ? ` · ${c.space_name}` : ""}
                    </span>
                    <TagChips tags={c.tags} />
                  </NavLink>
                )}
              </li>
            ))}
          </ul>
          {metadataOnly ? (
            <Badge variant="muted">
              Titles and sizes only. Messages stay with their owners.
            </Badge>
          ) : null}
        </nav>
        <div className="conv__main">
          {id ? (
            <ThreadView
              key={id}
              conversationId={id}
              onDeleted={() => navigate("/conversations")}
            />
          ) : (
            <p className="text-muted">
              Pick a conversation, or start a new one.
            </p>
          )}
        </div>
      </div>
      <SpacesDialog
        open={managingSpaces}
        onClose={() => setManagingSpaces(false)}
      />
      <NewConversationDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreate={(body) => create.mutate(body)}
        busy={create.isPending}
      />
    </div>
  );
}
