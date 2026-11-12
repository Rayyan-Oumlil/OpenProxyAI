import { useId, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type {
  Conversation,
  ConversationUpdate,
} from "../../api/conversationTypes";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
import { friendlyError } from "../../lib/conversations";
import { composeTags, hasPrivateTag, withoutPrivate } from "../../lib/tags";
import { useAuth } from "../../state/AuthContext";
import { SpacePicker } from "./SpacePicker";

/** Tags and space of a conversation you own. The "private" tag pulls a shared conversation back to private and blocks sharing it. */
export function DetailsDialog({
  conversation,
  open,
  onClose,
}: {
  conversation: Conversation;
  open: boolean;
  onClose: () => void;
}) {
  const { token } = useAuth();
  const qc = useQueryClient();
  const ids = { tags: useId(), space: useId(), priv: useId() };
  const [tags, setTags] = useState(
    withoutPrivate(conversation.tags).join(", "),
  );
  const [keepPrivate, setKeepPrivate] = useState(
    hasPrivateTag(conversation.tags),
  );
  const [spaceId, setSpaceId] = useState(conversation.space_id ?? "");
  const wasShared = conversation.visibility !== "private";

  const save = useMutation({
    mutationFn: (body: ConversationUpdate) =>
      apiClient.patch<Conversation>(
        `/api/v1/conversations/${conversation.id}`,
        body,
        token!,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ["conversation", conversation.id],
      });
      void qc.invalidateQueries({ queryKey: ["conversations"] });
      void qc.invalidateQueries({ queryKey: ["spaces"] });
      toast.success("Details saved.");
      onClose();
    },
    onError: (e) =>
      toast.error(
        friendlyError(
          e instanceof Error ? e.message : "Could not save the details.",
        ),
      ),
  });

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Conversation details</DialogTitle>
          <DialogDescription>
            Tags and spaces help you find a conversation. They do not change who
            can read it.
          </DialogDescription>
        </DialogHeader>
        <form
          className="stack-form"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate({
              tags: composeTags(tags, keepPrivate),
              space_id: spaceId || null,
            });
          }}
        >
          <label className="inline-control" htmlFor={ids.tags}>
            Tags (comma separated)
            <input
              id={ids.tags}
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="e.g. finance, q3"
            />
          </label>
          <SpacePicker id={ids.space} value={spaceId} onChange={setSpaceId} />
          <label className="flex items-center gap-2 text-sm" htmlFor={ids.priv}>
            <input
              id={ids.priv}
              type="checkbox"
              checked={keepPrivate}
              onChange={(e) => setKeepPrivate(e.target.checked)}
            />
            Keep private (adds the &ldquo;private&rdquo; tag; it can then never
            be shared)
          </label>
          {keepPrivate && wasShared ? (
            <p role="note" className="text-muted text-sm">
              This conversation is shared now. Saving stops sharing it.
            </p>
          ) : null}
          <DialogFooter>
            <button type="button" className="btn-outline" onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              disabled={save.isPending}
              className="bg-accent-sky"
            >
              Save details
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
