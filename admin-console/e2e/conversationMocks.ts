/** API fixtures for the conversation screens. */

export const CONVERSATION = {
  id: "c1", title: "Q3 review", visibility: "private", team_id: null, tags: ["finance"], owner_id: "u1", owner_email: "admin@example.com",
  is_owner: true, turn_count: 2, created_at: "2026-11-01T10:00:00Z", updated_at: "2026-11-01T10:00:00Z",
};

export const TURNS = [
  { id: "t1", seq: 1, role: "user", content: "Project Falcon price?", data_class: "confidential", model: null, created_at: "2026-11-01T10:00:00Z" },
  { id: "t2", seq: 2, role: "assistant", content: "About 4.2 billion.", data_class: "confidential", model: "openai/gpt-4o", created_at: "2026-11-01T10:00:05Z" },
];

export const CONTEXT = {
  package_id: "p1", model: "anthropic/claude", data_class: "internal", routing_mode: "enforce", included_turn_ids: [],
  withheld: [{ turn_id: "t1", seq: 1, reason: "above_clearance" }, { turn_id: "t2", seq: 2, reason: "above_clearance" }],
  estimated_tokens: 12, payload_sha256: "a".repeat(64), outcome: "ok", created_at: "2026-11-01T10:01:00Z",
};

export function conversationMock(pathname: string): unknown | undefined {
  if (pathname === "/api/v1/conversations") return [CONVERSATION];
  if (pathname === "/api/v1/conversations/models") return [{ model_id: "openai/gpt-4o", max_data_class: "confidential" }, { model_id: "anthropic/claude", max_data_class: "internal" }];
  if (pathname === "/api/v1/conversations/teams") return [{ id: "team1", name: "Finance" }];
  if (pathname === "/api/v1/conversations/c1") return CONVERSATION;
  if (pathname === "/api/v1/conversations/c1/turns") return TURNS;
  if (pathname === "/api/v1/conversations/c1/turns/t2/context") return CONTEXT;
  return undefined;
}
