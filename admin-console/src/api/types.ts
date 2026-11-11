export type LoginRequest = {
  email: string;
  password: string;
};

export type RegisterRequest = {
  email: string;
  password: string;
  name: string;
  org_name: string;
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
  p50_latency_ms?: number | null;
  p95_latency_ms?: number | null;
  p99_latency_ms?: number | null;
  projected_month_end_cost_usd?: number | null;
  forecast_basis_days?: number | null;
  cache_hit_rate?: number | null;
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

export type CostByKey = {
  api_key_id: string;
  name: string | null;
  key_prefix: string;
  requests: number;
  tokens: number;
  cost_usd: number;
};

export type CostByTeam = {
  team_id: string;
  name: string;
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
  by_key?: CostByKey[];
  by_team: CostByTeam[];
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
  team_id: string | null;
};

export type ApiKeyCreatedResponse = ApiKeyResponse & {
  key: string;
  warning: string;
};

export type CreateApiKeyRequest = {
  name: string;
  permissions: string[];
  expires_at: string | null;
  team_id?: string | null;
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
  data_region?: string | null;
  created_at: string;
  stripe_customer_id?: string | null;
  stripe_subscription_id?: string | null;
  stripe_subscription_status?: string | null;
  /** Set for usage-metered plans — monthly included token allowance. */
  included_tokens_monthly?: number | null;
};

export type OrganizationUpdateRequest = {
  name?: string;
  plan?: string;
  settings?: Record<string, unknown>;
  budget_monthly_usd?: number | null;
  is_active?: boolean;
  data_region?: string | null;
};

export type CheckoutResponse = {
  checkout_url: string;
};

export type PortalResponse = {
  portal_url: string;
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

/** Least to most sensitive. A key's max_data_class is the most sensitive data its endpoint may receive. */
export type DataClass = "public" | "internal" | "confidential" | "secret";

export type ProviderKeyResponse = {
  id: string;
  provider: string;
  alias: string | null;
  key_alias: string;
  key_prefix: string;
  weight: number;
  is_active: boolean;
  region: string;
  /** Custom endpoint (vLLM, Ollama, private gateway); null means the provider's own */
  api_base?: string | null;
  max_data_class?: DataClass;
  /** Endpoint is inside the customer's own network */
  is_internal?: boolean;
  model_patterns: string[] | null;
  created_at: string;
  /** Unix timestamp when circuit closes; null if closed (circuit breaker state) */
  circuit_open_until?: number | null;
  /** Adaptive LB: p99 latency (ms) from recent request_logs */
  latency_p99_ms?: number | null;
  /** Adaptive LB: error rate (0–1) from recent request_logs */
  error_rate?: number | null;
  /** Adaptive LB: effective weight used in key selection */
  effective_weight?: number | null;
  /** Provider health-check job: unknown until the first check has run */
  health_status?: string;
  consecutive_failures?: number;
  last_health_check_at?: string | null;
};

export type CreateProviderKeyRequest = {
  provider: string;
  alias?: string;
  key_alias?: string;
  api_key: string;
  weight?: number;
  region?: string;
  api_base?: string | null;
  max_data_class?: DataClass;
  is_internal?: boolean;
  model_patterns?: string[] | null;
};

export type UpdateProviderKeyRequest = {
  alias?: string;
  key_alias?: string;
  weight?: number;
  is_active?: boolean;
  region?: string;
  api_base?: string | null;
  max_data_class?: DataClass;
  is_internal?: boolean;
  model_patterns?: string[] | null;
};

export type Rating = "low" | "medium" | "high";

export type ModelRegistryEntry = {
  id: string;
  model_id: string;
  provider: string;
  /** null once the key was deleted: the entry is kept but cannot be routed */
  provider_key_id: string | null;
  max_data_class: DataClass;
  regions: string[];
  risk_rating: Rating;
  retention_days: number | null;
  trains_on_data: boolean;
  capabilities: string[];
  cost_tier: Rating | null;
  owner: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type CreateModelRegistryRequest = {
  model_id: string;
  provider_key_id?: string | null;
  max_data_class?: DataClass;
  regions: string[];
  risk_rating?: Rating;
  retention_days?: number | null;
  trains_on_data?: boolean;
  capabilities?: string[];
  cost_tier?: Rating | null;
  owner?: string | null;
  enabled?: boolean;
};

export type UpdateModelRegistryRequest = Partial<Omit<CreateModelRegistryRequest, "model_id">>;

export type PolicyConfigRequest = {
  enforcement_mode?: "off" | "observe" | "log_only" | "enforce";
  allowed_models?: string[];
  blocked_keywords?: string[];
  pii_detection_enabled?: boolean;
  pii_entities?: string[];
  model_rate_limits?: Record<string, { rpm?: number; tpm?: number }>;
  prompt_injection_detection_enabled?: boolean;
  response_guardrails_enabled?: boolean;
  response_pii_redact?: boolean;
  /** The class of a request that shows no sign of being more sensitive */
  default_data_class?: DataClass;
  /** Kind of PII found (e.g. "ssn") to the class it raises a request to; overrides the built-in defaults */
  data_class_map?: Record<string, DataClass>;
  /** off: nothing changes; log_only: decide and record, never refuse; enforce: only authorized registry models may serve */
  routing_mode?: RoutingMode;
  /** Registry models rated above this are never authorized */
  max_risk_rating?: Rating;
  /** Share (0 to 1) of delivered requests whose redacted prompt and answer are kept for evaluation. 0 stores nothing. */
  payload_capture_sample_rate?: number;
  /** An edited prompt template becomes a draft that needs a passing eval run (or an audited override) to go live */
  prompt_promotion_gate?: boolean;
  prompt_gate_min_pass_rate?: number;
  prompt_gate_min_items?: number;
  /** Lets users keep conversations in the gateway. Off by default: it stores what users said. */
  conversations_enabled?: boolean;
  /** Lets /v1/responses keep state at the provider (store=true, previous_response_id, file references). Off by default. */
  allow_provider_response_state?: boolean;
};

export type RoutingMode = "off" | "log_only" | "enforce";

export type PolicyPreviewRequest = {
  model: string;
  messages: { role: "user"; content: string }[];
  data_class?: DataClass;
  fallback_model?: string;
};

export type PolicyPreviewVerdict = "allowed" | "blocked_by_policy" | "blocked_by_routing" | "would_block_if_enforced";

export type PolicyPreviewResponse = {
  verdict: PolicyPreviewVerdict;
  data_class: { class: DataClass; source: string; entities: string[] };
  policy: { mode: string; allowed: boolean; action: string; reason_code: string | null; detail: string | null; triggered_rules: string[] };
  routing: {
    current_mode: RoutingMode;
    requested: string;
    model: string | null;
    reason: string;
    authorized: string[];
    excluded: Record<string, string>;
    key_alias: string | null;
  };
  fallback: { model: string; authorized: boolean; reason: string } | null;
  /** What a real request also goes through that a preview skips */
  not_evaluated: string[];
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

export type PolicyTemplate = {
  name: string;
  description: string;
  configures: string[];
};

export type ApplyTemplateRequest = {
  template: "healthcare_hipaa" | "finance_pci" | "government_fedramp";
};

export type PromptTemplate = {
  id: string;
  org_id: string;
  name: string;
  description: string | null;
  system_message: string | null;
  user_template: string;
  variables_schema: Array<{ name: string; type?: string; default?: string; required?: boolean }>;
  version: number;
  is_active: boolean;
  /** draft (waiting for promotion), active (live) or retired. Absent on gateways older than the promotion gate. */
  status?: "draft" | "active" | "retired";
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type PlaygroundCompareRequest = {
  models: string[];
  messages: Array<{ role: string; content: string }>;
  temperature?: number | null;
  max_tokens?: number | null;
};

export type PlaygroundCompareResult = {
  model: string;
  content: string;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
  latency_ms: number;
  ttft_ms: number | null;
  error: string | null;
};

export type PlaygroundCompareResponse = {
  results: PlaygroundCompareResult[];
};

export type TeamResponse = {
  id: string;
  org_id: string;
  name: string;
  budget_monthly_usd: string | null;
  created_at: string;
  member_count: number;
};

export type TeamDetailResponse = TeamResponse & {
  members: Array<{ id: string; email: string; name: string | null }>;
};

export type CreateTeamRequest = {
  name: string;
  budget_monthly_usd?: number | null;
};

export type UpdateTeamRequest = {
  name?: string | null;
  budget_monthly_usd?: number | null;
};

export type InviteResponse = {
  id: string;
  org_id: string;
  email: string;
  role: string;
  invited_by: string | null;
  expires_at: string;
  accepted_at: string | null;
  created_at: string;
};

export type InviteCreatedResponse = InviteResponse & {
  invite_url: string;
};

export type InviteCreateRequest = {
  email: string;
  role: "admin" | "developer" | "viewer";
};

export type AdminAuditLogEntry = {
  id: string;
  actor_email: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
};

export type ExperimentVariantResponse = {
  id: string;
  experiment_id: string;
  model: string;
  traffic_weight: number;
};

export type ExperimentResponse = {
  id: string;
  org_id: string;
  name: string;
  target_model: string;
  is_active: boolean;
  variants: ExperimentVariantResponse[];
  created_at: string;
  /** static: the weights are whatever an admin set. adaptive: a job moves them and stops the test with a winner. */
  mode?: "static" | "adaptive";
  metric?: string | null;
  min_samples_per_variant?: number;
  delta?: number;
  weight_floor?: number;
  winner_variant_id?: string | null;
  stopped_reason?: "winner" | "manual" | null;
  adaptive_error?: string | null;
};

export type AdaptiveSettings = {
  mode?: "static" | "adaptive";
  metric?: string;
  min_samples_per_variant?: number;
  delta?: number;
  weight_floor?: number;
};

export type CreateExperimentRequest = AdaptiveSettings & {
  name: string;
  target_model: string;
  variants: Array<{ model: string; traffic_weight: number }>;
};

export type UpdateExperimentRequest = AdaptiveSettings & {
  name?: string;
  is_active?: boolean;
  /** Replaces every variant, which also detaches the ratings collected so far: send it only when it changed. */
  variants?: Array<{ model: string; traffic_weight: number }>;
};

export type ScoreAggregate = {
  name: string;
  avg: number;
  count: number;
};

export type VariantMetrics = {
  variant_id?: string | null;
  traffic_weight?: number | null;
  /** Adaptive tests only: the chance this variant is the best one */
  probability_best?: number | null;
  model: string;
  request_count: number;
  avg_latency_ms: number | null;
  total_cost_usd: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  policy_violations: number;
  scores?: ScoreAggregate[];
};

export type AdaptiveStatus = {
  metric: string;
  ready: boolean;
  min_samples_per_variant: number;
  delta: number;
  samples: Record<string, number>;
  winner_variant_id: string | null;
  stopped_reason: string | null;
  error: string | null;
};

export type ExperimentResultsResponse = {
  variants: VariantMetrics[];
  adaptive?: AdaptiveStatus | null;
};
