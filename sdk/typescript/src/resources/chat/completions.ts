import type { APIClient } from '../../core/api-client.js';
import { streamSSE } from '../../core/streaming.js';
import type {
  ChatCompletion,
  ChatCompletionChunk,
  ChatCompletionCreateParams,
} from '../../types/chat.js';

export class ChatCompletionsResource {
  constructor(private readonly client: APIClient) {}

  async create(params: ChatCompletionCreateParams & { stream?: false }): Promise<ChatCompletion>;
  async create(
    params: ChatCompletionCreateParams & { stream: true },
  ): Promise<AsyncIterable<ChatCompletionChunk>>;
  async create(
    params: ChatCompletionCreateParams,
  ): Promise<ChatCompletion | AsyncIterable<ChatCompletionChunk>> {
    if (params.stream) {
      const response = await this.client.streamRequest({
        method: 'POST',
        path: '/v1/chat/completions',
        body: params,
        stream: true,
      });

      if (!response.ok) {
        throw new Error(`Stream request failed: ${response.status}`);
      }

      const gatewayMeta = {
        requestId: response.headers.get('x-openproxyai-request-id') ?? undefined,
        provider: response.headers.get('x-openproxyai-provider') ?? undefined,
      };

      return streamSSE(response, gatewayMeta);
    }

    const { data, gateway } = await this.client.request<ChatCompletion>({
      method: 'POST',
      path: '/v1/chat/completions',
      body: params,
    });

    return { ...data, gateway };
  }
}

export class ChatResource {
  readonly completions: ChatCompletionsResource;

  constructor(client: APIClient) {
    this.completions = new ChatCompletionsResource(client);
  }
}
