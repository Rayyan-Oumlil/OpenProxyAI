export interface Message {
  role: 'system' | 'user' | 'assistant' | 'function';
  content: string | null;
  name?: string;
}

export interface Delta {
  role?: string;
  content?: string | null;
}

export interface Choice {
  index: number;
  message: Message;
  finish_reason: string | null;
  logprobs?: unknown;
}

export interface StreamChoice {
  index: number;
  delta: Delta;
  finish_reason: string | null;
}

export interface Usage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface GatewayMeta {
  requestId?: string;
  costUsd?: number;
  latencyMs?: number;
  provider?: string;
  policyAction?: string;
}

export interface ChatCompletion {
  id: string;
  object: 'chat.completion';
  created: number;
  model: string;
  choices: Choice[];
  usage: Usage;
  gateway: GatewayMeta;
}

export interface ChatCompletionChunk {
  id: string;
  object: 'chat.completion.chunk';
  created: number;
  model: string;
  choices: StreamChoice[];
  gateway: GatewayMeta;
}

export interface ChatCompletionCreateParams {
  model: string;
  messages: Message[];
  stream?: boolean;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  frequency_penalty?: number;
  presence_penalty?: number;
  stop?: string | string[];
  n?: number;
  user?: string;
  [key: string]: unknown;
}
