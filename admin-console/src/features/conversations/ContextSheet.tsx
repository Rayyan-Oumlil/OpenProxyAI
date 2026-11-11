import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../../api/client";
import type { ContextSummary, Turn } from "../../api/conversationTypes";
import { Badge } from "../../components/ui/badge";
import { Fact } from "../../components/ui/Fact";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "../../components/ui/sheet";
import { REASON_LABEL, turnBySeq } from "../../lib/conversations";
import { dataClassLabel } from "../../lib/dataClasses";
import { formatDateTime } from "../../lib/utils";
import { useAuth } from "../../state/AuthContext";

const MODE_LABEL: Record<string, string> = {
  off: "Routing off: everything was sent",
  log_only: "Routing in preview: everything was sent",
  enforce: "Routing enforced",
};

function preview(text: string): string {
  return text.length > 140 ? `${text.slice(0, 140)}…` : text;
}

/** What one answer was built from. Opened from an answer's "Context sent" button. */
export function ContextSheet({
  conversationId,
  turn,
  turns,
  onClose,
}: {
  conversationId: string;
  turn: Turn | null;
  turns: readonly Turn[];
  onClose: () => void;
}) {
  const { token } = useAuth();
  const query = useQuery({
    queryKey: ["conversation-context", conversationId, turn?.id],
    queryFn: () =>
      apiClient.get<ContextSummary>(
        `/api/v1/conversations/${conversationId}/turns/${turn!.id}/context`,
        token!,
      ),
    enabled: Boolean(token && turn),
  });
  const context = query.data;

  return (
    <Sheet
      open={turn !== null}
      onOpenChange={(open) => (open ? undefined : onClose())}
    >
      <SheetContent aria-describedby={undefined}>
        <SheetHeader>
          <SheetTitle>Context sent to the model</SheetTitle>
        </SheetHeader>
        <SheetBody>
          {query.isLoading ? <p className="text-muted">Loading…</p> : null}
          {query.isError ? (
            <p role="alert">
              Could not load what was sent:{" "}
              {query.error instanceof Error
                ? query.error.message
                : "unknown error"}
            </p>
          ) : null}
          {context ? (
            <>
              <dl className="trace-facts">
                <Fact label="Model">{context.model}</Fact>
                <Fact label="Class of what was sent">
                  <Badge variant="policy">
                    {dataClassLabel(context.data_class)}
                  </Badge>
                </Fact>
                <Fact label="Routing">
                  {MODE_LABEL[context.routing_mode] ?? context.routing_mode}
                </Fact>
                <Fact label="Earlier messages sent">
                  {context.included_turn_ids.length}
                </Fact>
                <Fact label="Earlier messages held back">
                  {context.withheld.length}
                </Fact>
                <Fact label="Size (estimate)">
                  {context.estimated_tokens} tokens
                </Fact>
                <Fact label="Recorded">
                  {formatDateTime(context.created_at)}
                </Fact>
                <Fact label="Fingerprint">
                  <code title="SHA-256 of the exact messages sent. It lets an auditor check a claim about what a provider received.">
                    {context.payload_sha256.slice(0, 16)}…
                  </code>
                </Fact>
              </dl>
              <h3 className="mt-4">Held back</h3>
              {context.withheld.length === 0 ? (
                <p className="text-muted text-sm">
                  Nothing. The model saw the whole conversation that fit.
                </p>
              ) : (
                <ul className="withheld-list">
                  {context.withheld.map((w) => {
                    const held = turnBySeq(turns, w.seq);
                    return (
                      <li key={w.turn_id}>
                        <div className="flex items-center gap-2">
                          <strong>
                            #{w.seq}{" "}
                            {held
                              ? held.role === "user"
                                ? "You"
                                : "Assistant"
                              : ""}
                          </strong>
                          {held ? (
                            <Badge variant="muted">
                              {dataClassLabel(held.data_class)}
                            </Badge>
                          ) : null}
                        </div>
                        <div className="text-sm text-muted">
                          {REASON_LABEL[w.reason]}
                        </div>
                        {held ? (
                          <div className="text-sm">{preview(held.content)}</div>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              )}
            </>
          ) : null}
        </SheetBody>
      </SheetContent>
    </Sheet>
  );
}
