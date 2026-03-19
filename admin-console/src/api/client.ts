import type { PlaygroundCompareRequest, PlaygroundCompareResponse, PromptTemplate } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type RequestOptions = {
  token?: string;
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
};

async function request<T>(path: string, options: RequestOptions): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    const errorData = (await response.json().catch(() => null)) as
      | { detail?: string; error?: string }
      | null;
    const message =
      errorData?.detail ?? errorData?.error ?? `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

async function requestBlob(path: string, options: RequestOptions): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers: {
      ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
    },
  });

  if (!response.ok) {
    const errorData = (await response.json().catch(() => null)) as
      | { detail?: string; error?: string }
      | null;
    const message =
      errorData?.detail ?? errorData?.error ?? `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  return response.blob();
}

export const apiClient = {
  get: <T>(path: string, token?: string) => request<T>(path, { method: "GET", token }),
  post: <T>(path: string, body: unknown, token?: string) =>
    request<T>(path, { method: "POST", body, token }),
  put: <T>(path: string, body: unknown, token?: string) =>
    request<T>(path, { method: "PUT", body, token }),
  patch: <T>(path: string, body: unknown, token?: string) =>
    request<T>(path, { method: "PATCH", body, token }),
  del: <T>(path: string, token?: string) => request<T>(path, { method: "DELETE", token }),
  getBlob: (path: string, token?: string) => requestBlob(path, { method: "GET", token }),
  createCheckoutSession: (plan: "starter" | "growth", token?: string) =>
    request<{ checkout_url: string }>("/api/v1/billing/checkout", {
      method: "POST",
      body: { plan },
      token,
    }),
  createPortalSession: (token?: string) =>
    request<{ portal_url: string }>("/api/v1/billing/portal", {
      method: "POST",
      body: {},
      token,
    }),
  getPromptTemplates: (token?: string) =>
    request<PromptTemplate[]>("/api/v1/prompt-templates", { method: "GET", token }),
  createPromptTemplate: (
    data: {
      name: string;
      description?: string | null;
      system_message?: string | null;
      user_template: string;
      variables_schema?: Array<{ name: string; type?: string; default?: string; required?: boolean }>;
    },
    token?: string
  ) =>
    request<PromptTemplate>("/api/v1/prompt-templates", { method: "POST", body: data, token }),
  updatePromptTemplate: (id: string, data: Partial<Pick<PromptTemplate, "name" | "description" | "system_message" | "user_template">>, token?: string) =>
    request<PromptTemplate>(`/api/v1/prompt-templates/${id}`, { method: "PUT", body: data, token }),
  deletePromptTemplate: (id: string, token?: string) =>
    request<void>(`/api/v1/prompt-templates/${id}`, { method: "DELETE", token }),
  compareModels: (data: PlaygroundCompareRequest, token?: string) =>
    request<PlaygroundCompareResponse>("/api/v1/playground/compare", { method: "POST", body: data, token }),
};
