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
