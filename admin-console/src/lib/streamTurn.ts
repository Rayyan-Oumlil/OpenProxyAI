import { API_BASE_URL } from "../api/client";
import type {
  ContextSummary,
  TurnExchange,
  TurnRequest,
} from "../api/conversationTypes";

export type StreamHandlers = {
  onContext: (
    context: Omit<
      ContextSummary,
      "package_id" | "payload_sha256" | "outcome" | "created_at"
    >,
  ) => void;
  onDelta: (text: string) => void;
};

export class StreamUnavailable extends Error {}

/** Splits a buffer of server-sent events into complete events and the unfinished remainder. */
export function parseEvents(buffer: string): {
  events: { event: string; data: unknown }[];
  rest: string;
} {
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  const events: { event: string; data: unknown }[] = [];
  for (const block of blocks) {
    const fields: Record<string, string> = {};
    for (const line of block.split("\n")) {
      const at = line.indexOf(": ");
      if (at > 0) fields[line.slice(0, at)] = line.slice(at + 2);
    }
    if (fields.event && fields.data)
      events.push({ event: fields.event, data: JSON.parse(fields.data) });
  }
  return { events, rest };
}

async function errorFrom(
  response: Response,
): Promise<{ code: string | null; message: string }> {
  const body = (await response.json().catch(() => null)) as {
    detail?: string | { error?: string; detail?: string };
  } | null;
  const detail = body?.detail;
  if (typeof detail === "string") return { code: null, message: detail };
  return {
    code: detail?.error ?? null,
    message: detail?.detail ?? `Request failed with status ${response.status}`,
  };
}

/**
 * Sends a message and reads the answer as it is written. Resolves with the stored exchange; rejects with the server's reason.
 * Throws StreamUnavailable when the organization cannot stream (its answers are checked before delivery), so the caller can ask again
 * without streaming.
 */
export async function streamTurn(
  conversationId: string,
  body: TurnRequest,
  token: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<TurnExchange> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${conversationId}/turns`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ ...body, stream: true }),
      signal,
    },
  );
  if (!response.ok) {
    const { code, message } = await errorFrom(response);
    if (code === "streaming_unavailable") throw new StreamUnavailable(message);
    throw new Error(message);
  }
  if (!response.body)
    throw new Error("This browser cannot read a streamed answer.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let done: TurnExchange | null = null;
  for (;;) {
    const { value, done: finished } = await reader.read();
    if (finished) break;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseEvents(buffer);
    buffer = parsed.rest;
    for (const { event, data } of parsed.events) {
      if (event === "context") handlers.onContext(data as never);
      else if (event === "delta")
        handlers.onDelta((data as { text: string }).text);
      else if (event === "done") done = data as TurnExchange;
      else if (event === "error")
        throw new Error(
          (data as { detail?: string }).detail ?? "The answer failed.",
        );
    }
  }
  if (!done)
    throw new Error(
      "The answer stopped before it finished. Nothing was saved.",
    );
  return done;
}
