import type { APIClient } from '../core/api-client.js';

export interface APIKeyResponse {
  id: string;
  name: string | null;
  key_prefix: string;
  permissions: string[];
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
}

export interface APIKeyCreateParams {
  name?: string;
  permissions?: string[];
  expires_at?: string;
}

export interface APIKeyCreatedResponse extends APIKeyResponse {
  key: string;
}

export class APIKeysResource {
  constructor(private readonly client: APIClient) {}

  async list(): Promise<APIKeyResponse[]> {
    const { data } = await this.client.request<APIKeyResponse[]>({
      method: 'GET',
      path: '/api/v1/api-keys',
    });
    return data;
  }

  async create(params: APIKeyCreateParams = {}): Promise<APIKeyCreatedResponse> {
    const { data } = await this.client.request<APIKeyCreatedResponse>({
      method: 'POST',
      path: '/api/v1/api-keys',
      body: params,
    });
    return data;
  }

  async delete(keyId: string): Promise<void> {
    await this.client.request<void>({
      method: 'DELETE',
      path: `/api/v1/api-keys/${keyId}`,
    });
  }
}
