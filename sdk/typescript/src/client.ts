import { APIClient } from './core/api-client.js';
import { ChatResource } from './resources/chat/completions.js';
import { EmbeddingsResource } from './resources/embeddings.js';
import { APIKeysResource } from './resources/api-keys.js';

export interface OpenProxyClientOptions {
  apiKey: string;
  baseUrl?: string;
}

const DEFAULT_BASE_URL = 'https://api.openproxyai.com';

export class OpenProxy {
  readonly chat: ChatResource;
  readonly embeddings: EmbeddingsResource;
  readonly apiKeys: APIKeysResource;

  private readonly _client: APIClient;

  constructor(options: OpenProxyClientOptions) {
    const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
    this._client = new APIClient(baseUrl, options.apiKey);
    this.chat = new ChatResource(this._client);
    this.embeddings = new EmbeddingsResource(this._client);
    this.apiKeys = new APIKeysResource(this._client);
  }
}
