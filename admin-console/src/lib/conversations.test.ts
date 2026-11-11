import { describe, expect, it } from "vitest";

import type { ContextSummary } from "../api/conversationTypes";
import {
  friendlyError,
  modelOptionLabel,
  withheldNotice,
} from "./conversations";

const base: ContextSummary = {
  package_id: "p",
  model: "anthropic/claude",
  data_class: "internal",
  routing_mode: "enforce",
  included_turn_ids: [],
  withheld: [],
  estimated_tokens: 1,
  payload_sha256: "x",
  outcome: "ok",
  created_at: "2026-11-01T10:00:00Z",
};

describe("withheldNotice", () => {
  it("is empty when nothing was held back", () => {
    expect(withheldNotice(base)).toBe("");
  });

  it("says one message, singular", () => {
    expect(
      withheldNotice({
        ...base,
        withheld: [{ turn_id: "a", seq: 1, reason: "above_clearance" }],
      }),
    ).toBe(
      "1 earlier message was not sent to anthropic/claude: 1 more sensitive than anthropic/claude is cleared for.",
    );
  });

  it("separates the two reasons", () => {
    const notice = withheldNotice({
      ...base,
      withheld: [
        { turn_id: "a", seq: 1, reason: "above_clearance" },
        { turn_id: "b", seq: 2, reason: "over_budget" },
        { turn_id: "c", seq: 3, reason: "over_budget" },
      ],
    });
    expect(notice).toContain("3 earlier messages were not sent");
    expect(notice).toContain(
      "1 more sensitive than anthropic/claude is cleared for, 2 left out to fit the context size",
    );
  });
});

describe("friendlyError", () => {
  it("rewrites the two errors a person can act on and leaves others alone", () => {
    expect(
      friendlyError("Conversations are not enabled for this organization."),
    ).toContain("turn them on under Policy");
    expect(
      friendlyError(
        "Another message in this conversation is still being answered.",
      ),
    ).toContain("Try again");
    expect(
      friendlyError("Not authorized for confidential data: not_in_registry"),
    ).toBe("Not authorized for confidential data: not_in_registry");
  });
});

describe("modelOptionLabel", () => {
  it("names the class, and shows an unknown one as it came", () => {
    expect(modelOptionLabel("openai/gpt-4o", "confidential")).toBe(
      "openai/gpt-4o (up to Confidential)",
    );
    expect(modelOptionLabel("x/y", "weird")).toBe("x/y (up to weird)");
  });
});
