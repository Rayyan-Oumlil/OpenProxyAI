import { APIClient } from './core/api-client.js';
import { ChatResource } from './resources/chat/completions.js';
import { EmbeddingsResource } from './resources/embeddings.js';
import { APIKeysResource } from './resources/api-keys.js';
import {
  AudioResource,
  BatchesResource,
  FeedbackResource,
  FilesResource,
  ImagesResource,
  ModelsResource,
  RerankResource,
  ResponsesResource,
} from './resources/gateway.js';

export interface OpenProxyClientOptions {
  apiKey: string;
  baseUrl?: string;
}

const DEFAULT_BASE_URL = 'https://api.openproxyai.com';

export class OpenProxy {
  readonly chat: ChatResource;
  readonly embeddings: EmbeddingsResource;
  readonly apiKeys: APIKeysResource;
  readonly models: ModelsResource;
  readonly rerank: RerankResource;
  readonly images: ImagesResource;
  readonly audio: AudioResource;
  readonly responses: ResponsesResource;
  readonly feedback: FeedbackResource;
  readonly files: FilesResource;
  readonly batches: BatchesResource;

  private readonly _client: APIClient;

  constructor(options: OpenProxyClientOptions) {
    const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
    this._client = new APIClient(baseUrl, options.apiKey);
    this.chat = new ChatResource(this._client);
    this.embeddings = new EmbeddingsResource(this._client);
    this.apiKeys = new APIKeysResource(this._client);
    this.models = new ModelsResource(this._client);
    this.rerank = new RerankResource(this._client);
    this.images = new ImagesResource(this._client);
    this.audio = new AudioResource(this._client);
    this.responses = new ResponsesResource(this._client);
    this.feedback = new FeedbackResource(this._client);
    this.files = new FilesResource(this._client);
    this.batches = new BatchesResource(this._client);
  }
}
