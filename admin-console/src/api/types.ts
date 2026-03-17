export type LoginRequest = {
  email: string;
  password: string;
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

export type UserMeResponse = {
  id: string;
  org_id: string;
  email: string;
  name: string | null;
  role: string;
  is_active: boolean;
};

export type UsageOverview = {
  period_days: number;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_latency_ms: number;
  avg_ttft_ms: number;
  policy_blocked_requests: number;
  policy_flagged_requests: number;
};

export type CostByModel = {
  model: string;
  provider: string;
  requests: number;
  tokens: number;
  cost_usd: number;
};

export type CostByUser = {
  user_id: string;
  email: string;
  requests: number;
  tokens: number;
  cost_usd: number;
};

export type DailyUsageTrend = {
  date: string;
  requests: number;
  tokens: number;
  cost_usd: number;
  avg_latency_ms: number;
};

export type AnalyticsResponse = {
  overview: UsageOverview;
  by_model: CostByModel[];
  by_user: CostByUser[];
  daily_trend: DailyUsageTrend[];
  generated_at: string;
};

export type RequestLogItem = {
  id: string;
  created_at: string;
  model: string;
  provider: string;
  status: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
  latency_ms: number | null;
  ttft_ms: number | null;
  error_message: string | null;
  policy_action: string | null;
  policy_reason: string | null;
};

export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

export type ApiKeyResponse = {
  id: string;
  name: string | null;
  key_prefix: string;
  permissions: string[];
  is_active: boolean;
  expires_at: string | null;
  created_at: string;
};

export type ApiKeyCreatedResponse = ApiKeyResponse & {
  key: string;
  warning: string;
};

export type CreateApiKeyRequest = {
  name: string;
  permissions: string[];
  expires_at: string | null;
};

export type UserResponse = {
  id: string;
  org_id: string;
  email: string;
  name: string | null;
  role: "admin" | "developer" | "viewer";
  budget_daily_usd: string | null;
  budget_monthly_usd: string | null;
  is_active: boolean;
  created_at: string;
};

export type UserUpdateRequest = {
  name?: string | null;
  role?: "admin" | "developer" | "viewer";
  budget_daily_usd?: number | null;
  budget_monthly_usd?: number | null;
  is_active?: boolean;
};

export type OrganizationResponse = {
  id: string;
  name: string;
  slug: string;
  plan: string;
  settings: Record<string, unknown>;
  budget_monthly_usd: string | null;
  is_active: boolean;
  created_at: string;
};

export type OrganizationUpdateRequest = {
  name?: string;
  plan?: string;
  settings?: Record<string, unknown>;
  budget_monthly_usd?: number | null;
  is_active?: boolean;
};

export type PolicyAnalyticsResponse = {
  total_policy_events: number;
  by_action: { action: string; count: number }[];
  by_reason: { reason: string; count: number }[];
};

export type RequestLogDetail = RequestLogItem & {
  request_id: string | null;
  user_id: string | null;
  api_key_id: string | null;
  request_metadata: (Record<string, unknown> & { labels?: Record<string, string> }) | null;
  policy_triggered_rules: string[] | null;
};

export type ProviderKeyResponse = {
  id: string;
  provider: string;
  alias: string | null;
  key_prefix: string;
  weight: number;
  is_active: boolean;
  model_patterns: string[] | null;
  created_at: string;
};

export type CreateProviderKeyRequest = {
  provider: string;
  alias?: string;
  api_key: string;
  weight?: number;
  model_patterns?: string[] | null;
};

export type UpdateProviderKeyRequest = {
  alias?: string;
  weight?: number;
  is_active?: boolean;
  model_patterns?: string[] | null;
};

export type PolicyConfigRequest = {
  enforcement_mode?: "off" | "log_only" | "enforce";
  allowed_models?: string[];
  blocked_keywords?: string[];
  pii_detection_enabled?: boolean;
  pii_entities?: string[];
  model_rate_limits?: Record<string, { rpm?: number; tpm?: number }>;
  prompt_injection_detection_enabled?: boolean;
  response_guardrails_enabled?: boolean;
  response_pii_redact?: boolean;
};

export type PolicyConfigResponse = {
  enforcement_mode: string;
  allowed_models: string[];
  blocked_keywords: string[];
  pii_detection_enabled: boolean;
  pii_entities: string[];
  model_rate_limits: Record<string, { rpm?: number; tpm?: number }>;
  updated_at: string | null;
  prompt_injection_detection_enabled: boolean;
  response_guardrails_enabled: boolean;
  response_pii_redact: boolean;
};
