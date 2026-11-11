import type { DataClass } from "./types";

export type Visibility = "private" | "team";
export type ConversationScope = "mine" | "shared" | "org";

export type Conversation = {
  id: string;
  title: string;
  visibility: Visibility;
  team_id: string | null;
  tags: string[];
  owner_id: string;
  owner_email: string | null;
  is_owner: boolean;
  turn_count: number;
  created_at: string;
  updated_at: string;
};

export type ConversationCreate = {
  title: string;
  visibility?: Visibility;
  team_id?: string | null;
  tags?: string[];
};
export type ConversationUpdate = Partial<ConversationCreate>;

export type Turn = {
  id: string;
  seq: number;
  role: "user" | "assistant";
  content: string;
  data_class: string;
  model: string | null;
  created_at: string;
};

export type WithheldReason = "above_clearance" | "over_budget";
export type WithheldTurn = {
  turn_id: string;
  seq: number;
  reason: WithheldReason;
};

/** What one answer was built from: the earlier turns the model saw, the ones it did not, and a hash of the exact messages. */
export type ContextSummary = {
  package_id: string;
  model: string;
  data_class: string;
  routing_mode: string;
  included_turn_ids: string[];
  withheld: WithheldTurn[];
  estimated_tokens: number;
  payload_sha256: string;
  outcome: "ok" | "error";
  created_at: string;
};

export type TurnRequest = {
  content: string;
  model: string;
  data_class?: DataClass;
  system_prompt?: string;
};

export type TurnExchange = {
  user_turn: Turn;
  assistant_turn: Turn;
  context: ContextSummary;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: string;
};

export type TeamChoice = { id: string; name: string };
export type ModelChoice = { model_id: string; max_data_class: string };
