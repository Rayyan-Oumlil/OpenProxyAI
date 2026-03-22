import type { PlaygroundCompareRequest, PlaygroundCompareResponse, PromptTemplate } from "./types";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function parseApiError(response: Response): Promise<never> {
  const errorData = (await response.json().catch(() => null)) as
    | { detail?: string | Record<string, unknown>; error?: string }
    | null;
  const rawDetail = errorData?.detail;
  const message =
    (typeof rawDetail === "string"
      ? rawDetail
      : rawDetail && typeof rawDetail === "object" && "detail" in rawDetail
        ? String((rawDetail as { detail?: string }).detail ?? "")
        : null) ??
    errorData?.error ??
    `Request failed with status ${response.status}`;
  throw new Error(message || `Request failed with status ${response.status}`);
}

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
    await parseApiError(response);
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
    await parseApiError(response);
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
  createCheckoutSession: (plan: "starter" | "growth" | "metered", token?: string) =>
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
  getExperiments: (token?: string) =>
    request<import("./types").ExperimentResponse[]>("/api/v1/experiments", { method: "GET", token }),
  createExperiment: (data: import("./types").CreateExperimentRequest, token?: string) =>
    request<import("./types").ExperimentResponse>("/api/v1/experiments", { method: "POST", body: data, token }),
  getExperiment: (id: string, token?: string) =>
    request<import("./types").ExperimentResponse>(`/api/v1/experiments/${id}`, { method: "GET", token }),
  updateExperiment: (id: string, data: import("./types").UpdateExperimentRequest, token?: string) =>
    request<import("./types").ExperimentResponse>(`/api/v1/experiments/${id}`, { method: "PATCH", body: data, token }),
  deleteExperiment: (id: string, token?: string) =>
    request<void>(`/api/v1/experiments/${id}`, { method: "DELETE", token }),
  startExperiment: (id: string, token?: string) =>
    request<import("./types").ExperimentResponse>(`/api/v1/experiments/${id}/start`, { method: "POST", token }),
  stopExperiment: (id: string, token?: string) =>
    request<import("./types").ExperimentResponse>(`/api/v1/experiments/${id}/stop`, { method: "POST", token }),
  getExperimentResults: (id: string, token?: string) =>
    request<import("./types").ExperimentResultsResponse>(`/api/v1/experiments/${id}/results`, { method: "GET", token }),
  exchangeSsoCode: (code: string) =>
    request<import("./types").TokenResponse>("/api/v1/auth/sso/exchange-code", {
      method: "POST",
      body: { code },
    }),
};
