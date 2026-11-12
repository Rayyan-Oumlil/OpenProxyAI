import { afterEach, describe, expect, it, vi } from "vitest";

import type { TurnExchange } from "../api/conversationTypes";
import { StreamUnavailable, parseEvents, streamTurn } from "./streamTurn";

afterEach(() => vi.unstubAllGlobals());

describe("parseEvents", () => {
  it("returns complete events and keeps the unfinished remainder for the next chunk", () => {
    const first = parseEvents(
      'event: delta\ndata: {"text":"Hel"}\n\nevent: delta\ndata: {"te',
    );
    expect(first.events).toEqual([{ event: "delta", data: { text: "Hel" } }]);
    const second = parseEvents(first.rest + 'xt":"lo"}\n\n');
    expect(second.events).toEqual([{ event: "delta", data: { text: "lo" } }]);
    expect(second.rest).toBe("");
  });

  it("keeps colons and unicode inside the data", () => {
    expect(
      parseEvents('event: delta\ndata: {"text":"a: b, 日本語"}\n\n').events[0]
        .data,
    ).toEqual({ text: "a: b, 日本語" });
  });

  it("ignores a block with no data", () => {
    expect(parseEvents("event: ping\n\n").events).toEqual([]);
  });
});

function body(chunks: string[]) {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

const DONE = {
  assistant_turn: { content: "Hello" },
} as unknown as TurnExchange;
const sse = (event: string, data: unknown) =>
  `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

describe("streamTurn", () => {
  it("reports the text as it arrives, even split across reads, and resolves with the stored exchange", async () => {
    const text = [
      sse("context", { withheld: [] }),
      sse("delta", { text: "Hel" }),
      sse("delta", { text: "lo" }),
      sse("done", DONE),
    ].join("");
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            body([text.slice(0, 30), text.slice(30, 90), text.slice(90)]),
            { status: 200 },
          ),
      ),
    );
    const pieces: string[] = [];
    const onContext = vi.fn();
    const result = await streamTurn(
      "c1",
      { content: "hi", model: "openai/gpt-4o" },
      "tok",
      { onContext, onDelta: (t) => pieces.push(t) },
    );
    expect(pieces.join("")).toBe("Hello");
    expect(onContext).toHaveBeenCalledTimes(1);
    expect(result).toEqual(DONE);
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toContain("/api/v1/conversations/c1/turns");
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({
      content: "hi",
      model: "openai/gpt-4o",
      stream: true,
    });
    expect(
      ((init as RequestInit).headers as Record<string, string>).Authorization,
    ).toBe("Bearer tok");
  });

  it("rejects with the server's reason for a refusal before any stream", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              detail: { error: "refused", detail: "Not authorized" },
            }),
            { status: 446 },
          ),
      ),
    );
    await expect(
      streamTurn("c1", { content: "x", model: "m/x" }, "tok", {
        onContext: vi.fn(),
        onDelta: vi.fn(),
      }),
    ).rejects.toThrow("Not authorized");
  });

  it("throws StreamUnavailable when the organization cannot stream", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              detail: {
                error: "streaming_unavailable",
                detail: "checked first",
              },
            }),
            { status: 422 },
          ),
      ),
    );
    await expect(
      streamTurn("c1", { content: "x", model: "m/x" }, "tok", {
        onContext: vi.fn(),
        onDelta: vi.fn(),
      }),
    ).rejects.toBeInstanceOf(StreamUnavailable);
  });

  it("rejects with the error event's message when the answer breaks part-way", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            body([
              sse("delta", { text: "Hel" }),
              sse("error", { error: "model_error", detail: "stream broke" }),
            ]),
            { status: 200 },
          ),
      ),
    );
    await expect(
      streamTurn("c1", { content: "x", model: "m/x" }, "tok", {
        onContext: vi.fn(),
        onDelta: vi.fn(),
      }),
    ).rejects.toThrow("stream broke");
  });

  it("says nothing was saved when the stream ends with no final event", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(body([sse("delta", { text: "Hel" })]), { status: 200 }),
      ),
    );
    await expect(
      streamTurn("c1", { content: "x", model: "m/x" }, "tok", {
        onContext: vi.fn(),
        onDelta: vi.fn(),
      }),
    ).rejects.toThrow("Nothing was saved");
  });
});
