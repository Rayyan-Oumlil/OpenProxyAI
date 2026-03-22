import {
  AuthError,
  BudgetExceededError,
  OpenProxyError,
  PolicyViolationError,
  ProviderError,
  RateLimitError,
} from './errors.js';
import type { GatewayMeta } from '../types/chat.js';

export interface RequestOptions {
  method: string;
  path: string;
  body?: unknown;
  stream?: boolean;
}

const MAX_RETRIES = 3;
const BASE_DELAY_MS = 500;

function extractGatewayMeta(headers: Headers): GatewayMeta {
  return {
    requestId: headers.get('x-openproxyai-request-id') ?? undefined,
    costUsd: parseFloat(headers.get('x-openproxyai-cost-usd') ?? 'NaN') || undefined,
    latencyMs: parseInt(headers.get('x-openproxyai-latency-ms') ?? '', 10) || undefined,
    provider: headers.get('x-openproxyai-provider') ?? undefined,
    policyAction: headers.get('x-openproxyai-policy-action') ?? undefined,
  };
}

async function parseError(response: Response): Promise<OpenProxyError> {
  let body: Record<string, unknown> = {};
  try {
    body = (await response.json()) as Record<string, unknown>;
  } catch {
    // ignore parse failure
  }

  const status = response.status;

  if (status === 401 || status === 403) {
    const errorCode = body['error'] as string | undefined;
    if (errorCode === 'policy_violation') {
      const reason = (body['reason_code'] as string) ?? 'unknown';
      const rules = (body['triggered_rules'] as string[]) ?? [];
      return new PolicyViolationError(reason, rules);
    }
    return new AuthError((body['detail'] as string) ?? 'Unauthorized');
  }

  if (status === 429) {
    const errorCode = body['error'] as string | undefined;
    const limitType = (body['limit_type'] as string) ?? 'unknown';
    if (
      errorCode === 'budget_exceeded' ||
      limitType.includes('budget')
    ) {
      const budget = (body['daily_budget_usd'] as number) ?? 0;
      return new BudgetExceededError(budget);
    }
    const retryAfter = parseInt(response.headers.get('retry-after') ?? '60', 10);
    return new RateLimitError(limitType, retryAfter);
  }

  if (status === 502 || status === 504) {
    const provider = response.headers.get('x-openproxyai-provider') ?? 'unknown';
    return new ProviderError(status, provider);
  }

  return new OpenProxyError(
    (body['detail'] as string) ?? response.statusText,
    status,
  );
}

export class APIClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;

  constructor(baseUrl: string, apiKey: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.apiKey = apiKey;
  }

  async request<T>(options: RequestOptions): Promise<{ data: T; gateway: GatewayMeta }> {
    const url = `${this.baseUrl}${options.path}`;
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.apiKey}`,
      'Content-Type': 'application/json',
    };

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      const response = await fetch(url, {
        method: options.method,
        headers,
        body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      });

      if (response.ok) {
        const data = (await response.json()) as T;
        const gateway = extractGatewayMeta(response.headers);
        return { data, gateway };
      }

      const shouldRetry =
        attempt < MAX_RETRIES - 1 &&
        (response.status === 429 || response.status >= 500) &&
        response.status !== 403;

      if (!shouldRetry) {
        throw await parseError(response);
      }

      const delay = BASE_DELAY_MS * Math.pow(2, attempt);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }

    throw new OpenProxyError('Max retries exceeded', 500);
  }

  streamRequest(options: RequestOptions): Promise<Response> {
    const url = `${this.baseUrl}${options.path}`;
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.apiKey}`,
      'Content-Type': 'application/json',
    };

    return fetch(url, {
      method: options.method,
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  }
}
