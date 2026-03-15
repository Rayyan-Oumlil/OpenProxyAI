export class OpenProxyError extends Error {
  readonly statusCode: number;

  constructor(message: string, statusCode: number) {
    super(message);
    this.name = 'OpenProxyError';
    this.statusCode = statusCode;
  }
}

export class AuthError extends OpenProxyError {
  constructor(message = 'Authentication failed') {
    super(message, 401);
    this.name = 'AuthError';
  }
}

export class PolicyViolationError extends OpenProxyError {
  readonly reasonCode: string;
  readonly triggeredRules: string[];

  constructor(reasonCode: string, triggeredRules: string[] = []) {
    super(`Policy violation: ${reasonCode}`, 403);
    this.name = 'PolicyViolationError';
    this.reasonCode = reasonCode;
    this.triggeredRules = triggeredRules;
  }
}

export class RateLimitError extends OpenProxyError {
  readonly limitType: string;
  readonly retryAfter: number;

  constructor(limitType: string, retryAfter: number) {
    super(`Rate limit exceeded: ${limitType}`, 429);
    this.name = 'RateLimitError';
    this.limitType = limitType;
    this.retryAfter = retryAfter;
  }
}

export class BudgetExceededError extends OpenProxyError {
  readonly dailyBudgetUsd: number;

  constructor(dailyBudgetUsd: number) {
    super(`Daily budget of $${dailyBudgetUsd} exceeded`, 429);
    this.name = 'BudgetExceededError';
    this.dailyBudgetUsd = dailyBudgetUsd;
  }
}

export class ProviderError extends OpenProxyError {
  readonly provider: string;

  constructor(statusCode: number, provider: string) {
    super(`Provider error from ${provider}`, statusCode);
    this.name = 'ProviderError';
    this.provider = provider;
  }
}
