import { useId, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Send, Trash2, Users } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type {
  Conversation,
  ModelChoice,
  Turn,
  TurnExchange,
  TurnRequest,
} from "../../api/conversationTypes";
import type { DataClass } from "../../api/types";
import { Badge } from "../../components/ui/badge";
import { useConfirm } from "../../components/ui/ConfirmDialog";
import {
  friendlyError,
  modelOptionLabel,
  withheldNotice,
} from "../../lib/conversations";
import { DATA_CLASSES, dataClassLabel } from "../../lib/dataClasses";
import { formatDateTime } from "../../lib/utils";
import { useAuth } from "../../state/AuthContext";
import { ContextSheet } from "./ContextSheet";

const CONVERSATIONS = "/api/v1/conversations";

function TurnCard({
  turn,
  onShowContext,
}: {
  turn: Turn;
  onShowContext: (turn: Turn) => void;
}) {
  const mine = turn.role === "user";
  return (
    <article
      className={`turn ${mine ? "turn--user" : "turn--assistant"}`}
      aria-label={`${mine ? "You" : "Assistant"}, message ${turn.seq}`}
    >
      <header className="turn__meta">
        <strong>{mine ? "You" : "Assistant"}</strong>
        {turn.model ? (
          <span className="text-muted text-sm">{turn.model}</span>
        ) : null}
        <Badge
          variant={
            turn.data_class === "public" || turn.data_class === "internal"
              ? "muted"
              : "warning"
          }
        >
          {dataClassLabel(turn.data_class)}
        </Badge>
        <span className="text-muted text-sm">
          {formatDateTime(turn.created_at)}
        </span>
      </header>
      <p className="turn__body">{turn.content}</p>
      {!mine ? (
        <button
          type="button"
          className="btn-outline btn-small"
          onClick={() => onShowContext(turn)}
        >
          Context sent
        </button>
      ) : null}
    </article>
  );
}

function Composer({
  conversation,
  onSent,
}: {
  conversation: Conversation;
  onSent: (exchange: TurnExchange) => void;
}) {
  const { token } = useAuth();
  const ids = { model: useId(), cls: useId(), text: useId() };
  const [content, setContent] = useState("");
  const [model, setModel] = useState("");
  const [asserted, setAsserted] = useState<DataClass | "">("");
  const [error, setError] = useState<string | null>(null);

  const models = useQuery({
    queryKey: ["conversation-models"],
    queryFn: () =>
      apiClient.get<ModelChoice[]>(`${CONVERSATIONS}/models`, token!),
    enabled: Boolean(token),
  });
  const choices = models.data ?? [];
  const chosen = model || choices[0]?.model_id || "";

  const send = useMutation({
    mutationFn: (body: TurnRequest) =>
      apiClient.post<TurnExchange>(
        `${CONVERSATIONS}/${conversation.id}/turns`,
        body,
        token!,
      ),
    onSuccess: (exchange) => {
      setContent("");
      setAsserted(""); // a sensitivity applies to the message it was chosen for, not to the ones after it
      setError(null);
      onSent(exchange);
    },
    onError: (e) =>
      setError(
        friendlyError(
          e instanceof Error ? e.message : "The message could not be sent.",
        ),
      ),
  });

  return (
    <form
      className="composer"
      onSubmit={(e) => {
        e.preventDefault();
        if (!content.trim() || !chosen) return;
        send.mutate({
          content,
          model: chosen,
          ...(asserted ? { data_class: asserted } : {}),
        });
      }}
    >
      <div className="composer__row">
        <label className="inline-control" htmlFor={ids.model}>
          Model
          {models.isLoading ? (
            <select id={ids.model} disabled>
              <option>Loading models…</option>
            </select>
          ) : choices.length > 0 ? (
            <select
              id={ids.model}
              value={chosen}
              onChange={(e) => setModel(e.target.value)}
            >
              {choices.map((m) => (
                <option key={m.model_id} value={m.model_id}>
                  {modelOptionLabel(m.model_id, m.max_data_class)}
                </option>
              ))}
            </select>
          ) : (
            <input
              id={ids.model}
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="provider/model, e.g. openai/gpt-4o"
            />
          )}
        </label>
        <label className="inline-control" htmlFor={ids.cls}>
          Sensitivity
          <select
            id={ids.cls}
            value={asserted}
            onChange={(e) => setAsserted(e.target.value as DataClass | "")}
          >
            <option value="">Classified automatically</option>
            {DATA_CLASSES.map((c) => (
              <option key={c.value} value={c.value}>
                At least {c.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="inline-control" htmlFor={ids.text}>
        Message
        <textarea
          id={ids.text}
          className="textarea-short"
          value={content}
          maxLength={20000}
          onChange={(e) => setContent(e.target.value)}
        />
      </label>
      {error ? (
        <p role="alert" className="composer__error">
          {error}
        </p>
      ) : null}
      <div className="composer__actions">
        <button
          type="submit"
          className="bg-accent-sky"
          disabled={
            send.isPending || models.isLoading || !content.trim() || !chosen
          }
          aria-busy={send.isPending}
        >
          <Send size={14} aria-hidden="true" />{" "}
          {send.isPending ? "Sending…" : "Send"}
        </button>
      </div>
    </form>
  );
}

export function ThreadView({
  conversationId,
  onDeleted,
}: {
  conversationId: string;
  onDeleted: () => void;
}) {
  const { token } = useAuth();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [notice, setNotice] = useState("");
  const [inspecting, setInspecting] = useState<Turn | null>(null);

  const conversation = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () =>
      apiClient.get<Conversation>(`${CONVERSATIONS}/${conversationId}`, token!),
    enabled: Boolean(token),
  });
  const turns = useQuery({
    queryKey: ["conversation-turns", conversationId],
    queryFn: () =>
      apiClient.get<Turn[]>(`${CONVERSATIONS}/${conversationId}/turns`, token!),
    enabled: Boolean(token),
  });

  const remove = useMutation({
    mutationFn: () =>
      apiClient.del<void>(`${CONVERSATIONS}/${conversationId}`, token!),
    onSuccess: () => {
      toast.success("Conversation deleted.");
      void qc.invalidateQueries({ queryKey: ["conversations"] });
      onDeleted();
    },
    onError: (e) =>
      toast.error(
        e instanceof Error ? e.message : "Could not delete the conversation.",
      ),
  });

  if (conversation.isError)
    return (
      <p role="alert">
        This conversation does not exist or is not shared with you.
      </p>
    );
  if (!conversation.data) return <p className="text-muted">Loading…</p>;
  const c = conversation.data;
  const list = turns.data ?? [];

  return (
    <section className="thread" aria-label={`Conversation: ${c.title}`}>
      <header className="thread__head">
        <div>
          <h2>{c.title}</h2>
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
            <Badge variant={c.visibility === "team" ? "policy" : "muted"}>
              {c.visibility === "team" ? (
                <>
                  <Users size={12} aria-hidden="true" />
                  &nbsp;Shared with a team
                </>
              ) : c.visibility === "org" ? (
                "Shared with the organization"
              ) : (
                "Private"
              )}
            </Badge>
            {c.system_prompt ? (
              <Badge variant="default" title={c.system_prompt}>
                Has a standing instruction
              </Badge>
            ) : null}
            {c.tags.map((t) => (
              <Badge key={t} variant="default">
                {t}
              </Badge>
            ))}
            {!c.is_owner ? (
              <span>Read-only, owned by {c.owner_email ?? "a teammate"}</span>
            ) : null}
          </div>
        </div>
        {c.is_owner ? (
          <button
            type="button"
            className="btn-outline"
            onClick={async () => {
              if (
                await confirm({
                  title: "Delete this conversation?",
                  description:
                    "Its messages and the record of what was sent for each answer are removed. This cannot be undone.",
                  confirmLabel: "Delete",
                  destructive: true,
                })
              )
                remove.mutate();
            }}
          >
            <Trash2 size={14} aria-hidden="true" /> Delete
          </button>
        ) : null}
      </header>

      <div className="thread__turns">
        {list.length === 0 ? (
          <p className="text-muted">No messages yet.</p>
        ) : (
          list.map((t) => (
            <TurnCard key={t.id} turn={t} onShowContext={setInspecting} />
          ))
        )}
      </div>

      <div
        role="status"
        aria-live="polite"
        className={notice ? "thread__notice" : "sr-only"}
      >
        {notice}
      </div>

      {c.is_owner ? (
        <Composer
          conversation={c}
          onSent={(exchange) => {
            setNotice(withheldNotice(exchange.context));
            void qc.invalidateQueries({
              queryKey: ["conversation-turns", conversationId],
            });
            void qc.invalidateQueries({
              queryKey: ["conversation", conversationId],
            });
            void qc.invalidateQueries({ queryKey: ["conversations"] });
          }}
        />
      ) : null}

      <ContextSheet
        conversationId={conversationId}
        turn={inspecting}
        turns={list}
        onClose={() => setInspecting(null)}
      />
    </section>
  );
}
