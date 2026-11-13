import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import { OpenProxy, PolicyViolationError } from '../src/index.js';

const BASE_URL = 'http://localhost:8000';
const server = setupServer();
const client = new OpenProxy({ apiKey: 'opai_test', baseUrl: BASE_URL });

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('gateway endpoints', () => {
  it('lists models', async () => {
    server.use(http.get(`${BASE_URL}/v1/models`, () => HttpResponse.json({ data: [{ id: 'openai/gpt-4o' }] })));
    expect(((await client.models.list()).data as Array<{ id: string }>)[0].id).toBe('openai/gpt-4o');
  });

  it('reranks with the given fields', async () => {
    let seen: Record<string, unknown> = {};
    server.use(http.post(`${BASE_URL}/v1/rerank`, async ({ request }) => {
      seen = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({ results: [] });
    }));
    await client.rerank.create({ model: 'cohere/rerank', query: 'q', documents: ['a', 'b'], top_n: 1 });
    expect(seen.top_n).toBe(1);
  });

  it('returns speech as bytes', async () => {
    server.use(http.post(`${BASE_URL}/v1/audio/speech`, () => new HttpResponse(new Uint8Array([1, 2, 3]))));
    const audio = await client.audio.speech({ model: 'openai/tts-1', input: 'hi', voice: 'alloy' });
    expect(Array.from(audio)).toEqual([1, 2, 3]);
  });

  it('uploads a file as multipart and starts a batch', async () => {
    let contentType = '';
    let batchBody: Record<string, unknown> = {};
    server.use(
      http.post(`${BASE_URL}/v1/files`, ({ request }) => {
        contentType = request.headers.get('content-type') ?? '';
        return HttpResponse.json({ id: 'f1' });
      }),
      http.post(`${BASE_URL}/v1/batches`, async ({ request }) => {
        batchBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: 'b1', status: 'validating' });
      }),
    );
    const file = await client.files.create(new Blob(['{"custom_id":"1"}\n']));
    const batch = await client.batches.create({ input_file_id: file.id as string, max_cost_usd: 2.5 });
    expect(contentType).toMatch(/^multipart\/form-data; boundary=/);
    expect(batch.id).toBe('b1');
    expect(batchBody).toEqual({ input_file_id: 'f1', max_cost_usd: 2.5 });
  });

  it('drops unset feedback fields', async () => {
    let seen: Record<string, unknown> = {};
    server.use(http.post(`${BASE_URL}/v1/feedback`, async ({ request }) => {
      seen = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({ ok: true });
    }));
    await client.feedback.create({ request_id: 'r1', thumbs: 'up' });
    expect(seen).toEqual({ request_id: 'r1', thumbs: 'up' });
  });

  it('a policy block carries the end-user explanation', async () => {
    server.use(http.post(`${BASE_URL}/v1/responses`, () =>
      HttpResponse.json({ error: 'policy_violation', reason_code: 'pii_detected', explanation: 'That contains personal data.' }, { status: 446 })));
    const error = await client.responses.create({ model: 'openai/gpt-4o', input: 'x' }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(PolicyViolationError);
    expect((error as PolicyViolationError).explanation).toBe('That contains personal data.');
  });
});
