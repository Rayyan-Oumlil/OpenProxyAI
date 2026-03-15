import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import { OpenProxy } from '../src/index.js';

const BASE_URL = 'http://localhost:8000';

const SSE_CHUNKS = [
  'data: {"id":"chatcmpl-1","object":"chat.completion.chunk","created":1700000000,"model":"gpt-4o","choices":[{"index":0,"delta":{"role":"assistant","content":"Hello"},"finish_reason":null}]}',
  'data: {"id":"chatcmpl-1","object":"chat.completion.chunk","created":1700000000,"model":"gpt-4o","choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}',
  'data: {"id":"chatcmpl-1","object":"chat.completion.chunk","created":1700000000,"model":"gpt-4o","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
  'data: [DONE]',
].join('\n\n');

const server = setupServer();

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('chat.completions.create (streaming)', () => {
  it('yields chunks from SSE stream', async () => {
    server.use(
      http.post(`${BASE_URL}/v1/chat/completions`, () =>
        new HttpResponse(SSE_CHUNKS, {
          headers: {
            'content-type': 'text/event-stream',
            'x-openproxyai-provider': 'openai',
          },
        }),
      ),
    );

    const client = new OpenProxy({ apiKey: 'opai_test', baseUrl: BASE_URL });
    const stream = await client.chat.completions.create({
      model: 'openai/gpt-4o',
      messages: [{ role: 'user', content: 'Hello' }],
      stream: true,
    });

    const chunks: string[] = [];
    for await (const chunk of stream) {
      const content = chunk.choices[0]?.delta?.content;
      if (content) chunks.push(content);
    }

    expect(chunks.join('')).toBe('Hello!');
  });
});
