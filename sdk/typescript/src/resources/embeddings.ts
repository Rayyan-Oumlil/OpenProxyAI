import type { APIClient } from '../core/api-client.js';

export interface EmbeddingCreateParams {
  model: string;
  input: string | string[];
  encoding_format?: 'float' | 'base64';
  user?: string;
}

export interface Embedding {
  object: 'embedding';
  index: number;
  embedding: number[];
}

export interface EmbeddingResponse {
  object: 'list';
  data: Embedding[];
  model: string;
  usage: { prompt_tokens: number; total_tokens: number };
}

export class EmbeddingsResource {
  constructor(private readonly client: APIClient) {}

  async create(params: EmbeddingCreateParams): Promise<EmbeddingResponse> {
    const { data } = await this.client.request<EmbeddingResponse>({
      method: 'POST',
      path: '/v1/embeddings',
      body: params,
    });
    return data;
  }
}
