import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import { OpenProxy } from '../src/index.js';
import { PolicyViolationError, RateLimitError, AuthError } from '../src/index.js';

const BASE_URL = 'http://localhost:8000';

const MOCK_COMPLETION = {
  id: 'chatcmpl-123',
  object: 'chat.completion',
  created: 1700000000,
  model: 'gpt-4o',
  choices: [
    {
      index: 0,
      message: { role: 'assistant', content: 'Hello!' },
      finish_reason: 'stop',
    },
  ],
  usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
};

const server = setupServer();

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('chat.completions.create (non-streaming)', () => {
  it('returns a ChatCompletion with gateway meta', async () => {
    server.use(
      http.post(`${BASE_URL}/v1/chat/completions`, () =>
        HttpResponse.json(MOCK_COMPLETION, {
          headers: {
            'x-openproxyai-request-id': 'req-abc',
            'x-openproxyai-cost-usd': '0.00015',
            'x-openproxyai-provider': 'openai',
          },
        }),
      ),
    );

    const client = new OpenProxy({ apiKey: 'opai_test', baseUrl: BASE_URL });
    const result = await client.chat.completions.create({
      model: 'openai/gpt-4o',
      messages: [{ role: 'user', content: 'Hello' }],
    });

    expect(result.choices[0].message.content).toBe('Hello!');
    expect(result.gateway.requestId).toBe('req-abc');
    expect(result.gateway.costUsd).toBe(0.00015);
    expect(result.gateway.provider).toBe('openai');
  });

  it('throws PolicyViolationError on 403 policy_violation', async () => {
    server.use(
      http.post(`${BASE_URL}/v1/chat/completions`, () =>
        HttpResponse.json(
          { error: 'policy_violation', reason_code: 'pii_detected', triggered_rules: ['email'] },
          { status: 403 },
        ),
      ),
    );

    const client = new OpenProxy({ apiKey: 'opai_test', baseUrl: BASE_URL });
    await expect(
      client.chat.completions.create({
        model: 'openai/gpt-4o',
        messages: [{ role: 'user', content: 'my ssn is 123-45-6789' }],
      }),
    ).rejects.toThrow(PolicyViolationError);
  });

  it('throws RateLimitError on 429', async () => {
    server.use(
      http.post(`${BASE_URL}/v1/chat/completions`, () =>
        HttpResponse.json(
          { error: 'rate_limit_exceeded', limit_type: 'rpm' },
          { status: 429, headers: { 'retry-after': '30' } },
        ),
      ),
    );

    const client = new OpenProxy({ apiKey: 'opai_test', baseUrl: BASE_URL });
    await expect(
      client.chat.completions.create({
        model: 'openai/gpt-4o',
        messages: [{ role: 'user', content: 'hi' }],
      }),
    ).rejects.toThrow(RateLimitError);
  });

  it('throws AuthError on 401', async () => {
    server.use(
      http.post(`${BASE_URL}/v1/chat/completions`, () =>
        HttpResponse.json({ detail: 'Invalid API key' }, { status: 401 }),
      ),
    );

    const client = new OpenProxy({ apiKey: 'bad_key', baseUrl: BASE_URL });
    await expect(
      client.chat.completions.create({
        model: 'openai/gpt-4o',
        messages: [{ role: 'user', content: 'hi' }],
      }),
    ).rejects.toThrow(AuthError);
  });
});

describe('api-keys resource', () => {
  it('lists api keys', async () => {
    server.use(
      http.get(`${BASE_URL}/api/v1/api-keys`, () =>
        HttpResponse.json([
          { id: 'key-1', name: 'My Key', key_prefix: 'opai_abc', permissions: ['proxy:llm'], is_active: true, created_at: '2026-01-01T00:00:00Z', last_used_at: null, expires_at: null },
        ]),
      ),
    );

    const client = new OpenProxy({ apiKey: 'opai_test', baseUrl: BASE_URL });
    const keys = await client.apiKeys.list();
    expect(keys).toHaveLength(1);
    expect(keys[0].key_prefix).toBe('opai_abc');
  });
});
