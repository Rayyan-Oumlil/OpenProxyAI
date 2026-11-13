import type { APIClient } from '../core/api-client.js';

/** Raw bytes, a Blob, or a `[filename, bytes]` pair. */
export type FileInput = Blob | Uint8Array | [string, Blob | Uint8Array];

type Json = Record<string, unknown>;

function toBlob(part: Blob | Uint8Array): Blob {
  return part instanceof Blob ? part : new Blob([part as BlobPart]);
}

function upload(file: FileInput, defaultName: string, fields: Record<string, string>): FormData {
  const form = new FormData();
  for (const [key, value] of Object.entries(fields)) form.append(key, value);
  const [name, part] = Array.isArray(file) ? file : [defaultName, file];
  form.append('file', toBlob(part), name);
  return form;
}

function defined(fields: Json): Json {
  return Object.fromEntries(Object.entries(fields).filter(([, value]) => value !== undefined));
}

export class ModelsResource {
  constructor(private readonly client: APIClient) {}

  async list(): Promise<Json> {
    return (await this.client.request<Json>({ method: 'GET', path: '/v1/models' })).data;
  }
}

export interface RerankParams {
  model: string;
  query: string;
  documents: Array<string | { text: string }>;
  top_n?: number;
  return_documents?: boolean;
}

export class RerankResource {
  constructor(private readonly client: APIClient) {}

  async create(params: RerankParams): Promise<Json> {
    return (await this.client.request<Json>({ method: 'POST', path: '/v1/rerank', body: params })).data;
  }
}

export class ImagesResource {
  constructor(private readonly client: APIClient) {}

  async generate(params: { model: string; prompt: string } & Json): Promise<Json> {
    return (await this.client.request<Json>({ method: 'POST', path: '/v1/images/generations', body: params })).data;
  }
}

export class AudioResource {
  constructor(private readonly client: APIClient) {}

  /** Text to speech. Returns the audio bytes. */
  async speech(params: { model: string; input: string; voice: string } & Json): Promise<Uint8Array> {
    return (await this.client.request<Uint8Array>({ method: 'POST', path: '/v1/audio/speech', body: params, raw: true })).data;
  }

  /** Speech to text. Extra string fields (language, prompt) pass through as form fields. */
  async transcribe(model: string, file: FileInput, fields: Record<string, string> = {}): Promise<Json> {
    const form = upload(file, 'audio', { model, ...fields });
    return (await this.client.request<Json>({ method: 'POST', path: '/v1/audio/transcriptions', form })).data;
  }
}

export class ResponsesResource {
  constructor(private readonly client: APIClient) {}

  async create(params: { model: string; input: unknown } & Json): Promise<Json> {
    return (await this.client.request<Json>({ method: 'POST', path: '/v1/responses', body: params })).data;
  }
}

export interface FeedbackParams {
  request_id: string;
  /** Send exactly one of `thumbs` or `value`. */
  thumbs?: 'up' | 'down';
  value?: number;
  score_name?: string;
  comment?: string;
}

export class FeedbackResource {
  constructor(private readonly client: APIClient) {}

  /** `request_id` is the `x-openproxyai-request-id` response header of the request being rated. */
  async create(params: FeedbackParams): Promise<Json> {
    return (await this.client.request<Json>({ method: 'POST', path: '/v1/feedback', body: defined({ ...params }) })).data;
  }
}

export class FilesResource {
  constructor(private readonly client: APIClient) {}

  /** Upload a JSONL file of chat requests for a batch. */
  async create(file: FileInput, purpose = 'batch'): Promise<Json> {
    const form = upload(file, 'batch.jsonl', { purpose });
    return (await this.client.request<Json>({ method: 'POST', path: '/v1/files', form })).data;
  }

  async retrieve(fileId: string): Promise<Json> {
    return (await this.client.request<Json>({ method: 'GET', path: `/v1/files/${fileId}` })).data;
  }

  async content(fileId: string): Promise<Uint8Array> {
    return (await this.client.request<Uint8Array>({ method: 'GET', path: `/v1/files/${fileId}/content`, raw: true })).data;
  }

  async delete(fileId: string): Promise<Json> {
    return (await this.client.request<Json>({ method: 'DELETE', path: `/v1/files/${fileId}` })).data;
  }
}

export interface BatchCreateParams {
  input_file_id: string;
  /** Spending cap for the whole job. */
  max_cost_usd?: number;
  metadata?: Record<string, string>;
}

export class BatchesResource {
  constructor(private readonly client: APIClient) {}

  /** Run an uploaded file as one governed job. */
  async create(params: BatchCreateParams): Promise<Json> {
    return (await this.client.request<Json>({ method: 'POST', path: '/v1/batches', body: defined({ ...params }) })).data;
  }

  async retrieve(batchId: string): Promise<Json> {
    return (await this.client.request<Json>({ method: 'GET', path: `/v1/batches/${batchId}` })).data;
  }

  async list(limit = 20): Promise<Json> {
    return (await this.client.request<Json>({ method: 'GET', path: `/v1/batches?limit=${limit}` })).data;
  }

  async cancel(batchId: string): Promise<Json> {
    return (await this.client.request<Json>({ method: 'POST', path: `/v1/batches/${batchId}/cancel` })).data;
  }
}
