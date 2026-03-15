export interface CostByModel {
  model: string;
  cost_usd: number;
  total_requests: number;
}

export interface DailyTrend {
  day: string;
  cost_usd: number;
  total_requests: number;
  total_tokens: number;
}

export interface UsageOverview {
  total_requests: number;
  total_cost_usd: number;
  total_tokens: number;
  avg_latency_ms: number;
  cost_by_model: CostByModel[];
  daily_trend: DailyTrend[];
}
