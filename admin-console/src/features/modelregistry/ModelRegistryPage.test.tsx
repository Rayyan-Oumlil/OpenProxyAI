import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ModelRegistryEntry, ProviderKeyResponse } from "../../api/types";
import { ConfirmProvider } from "../../components/ui/ConfirmDialog";
import { ModelRegistryPage } from "./ModelRegistryPage";

vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ token: "tok", user: { role: "admin" } }) }));
vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { apiClient } from "../../api/client";
import { toast } from "sonner";

const get = vi.mocked(apiClient.get);
const post = vi.mocked(apiClient.post);
const patch = vi.mocked(apiClient.patch);
const del = vi.mocked(apiClient.del);

function entry(overrides: Partial<ModelRegistryEntry> = {}): ModelRegistryEntry {
  return {
    id: "m1",
    model_id: "openai/gpt-4o",
    provider: "openai",
    provider_key_id: "k1",
    max_data_class: "internal",
    regions: ["us"],
    risk_rating: "medium",
    retention_days: 30,
    trains_on_data: false,
    capabilities: ["CODE_GENERATION"],
    cost_tier: null,
    owner: "platform",
    enabled: true,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-01T10:00:00Z",
    ...overrides,
  };
}

function providerKey(overrides: Partial<ProviderKeyResponse> = {}): ProviderKeyResponse {
  return {
    id: "k1",
    provider: "openai",
    alias: null,
    key_alias: "primary",
    key_prefix: "sk-abc123",
    weight: 1,
    is_active: true,
    region: "us",
    model_patterns: null,
    created_at: "2026-11-01T10:00:00Z",
    ...overrides,
  };
}

function route(entries: ModelRegistryEntry[], keys: ProviderKeyResponse[] = [providerKey()]) {
  get.mockImplementation((path: string) => Promise.resolve((path.includes("model-registry") ? entries : keys) as never));
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ConfirmProvider>
        <ModelRegistryPage />
      </ConfirmProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  for (const fn of [get, post, patch, del]) fn.mockReset();
  vi.mocked(toast.error).mockReset();
  patch.mockResolvedValue(entry());
  post.mockResolvedValue(entry());
  del.mockResolvedValue(undefined as never);
});
afterEach(cleanup);

describe("ModelRegistryPage", () => {
  it("lists each model with its key, data class, regions, risk, retention and status", async () => {
    route([entry(), entry({ id: "m2", model_id: "anthropic/claude", provider_key_id: null, max_data_class: "confidential", regions: ["eu", "us"], risk_rating: "high", enabled: false, trains_on_data: true, retention_days: null })]);
    renderPage();
    const table = await screen.findByRole("table", { name: "Model registry" });
    await within(table).findByText("anthropic/claude");
    expect(within(table).getByText("openai/gpt-4o")).toBeTruthy();
    expect(within(table).getByText("primary")).toBeTruthy();
    expect(within(table).getByText("Not attached")).toBeTruthy();
    expect(within(table).getByText("Confidential")).toBeTruthy();
    expect(within(table).getByText("EU, US")).toBeTruthy();
    expect(within(table).getByText("30 d")).toBeTruthy();
    expect(within(table).getByText("Disabled")).toBeTruthy();
    expect(within(table).getByText("Yes")).toBeTruthy();
  });

  it("shows an empty state with the add button still available", async () => {
    route([]);
    renderPage();
    expect(await screen.findByText("No models yet")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add model" })).toBeTruthy();
  });

  it("keeps the header and offers a retry when loading fails", async () => {
    get.mockRejectedValue(new Error("boom"));
    renderPage();
    expect(await screen.findByText("Unable to load the model registry")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Model registry" })).toBeTruthy();
    expect(screen.getByText("Try again")).toBeTruthy();
  });

  it("adds a model, offering only provider keys that serve its provider", async () => {
    route([], [providerKey(), providerKey({ id: "k2", provider: "anthropic", key_alias: "claude-key" })]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Add model" }));
    fireEvent.change(screen.getByLabelText("Model"), { target: { value: "openai/gpt-4o" } });
    const select = screen.getByLabelText("Provider key") as HTMLSelectElement;
    expect(within(select).queryByText("claude-key")).toBeNull();
    fireEvent.change(select, { target: { value: "k1" } });
    fireEvent.change(screen.getByLabelText("Most sensitive data this model is cleared for"), { target: { value: "confidential" } });
    fireEvent.click(screen.getByLabelText("EU"));
    fireEvent.change(screen.getByLabelText("Capabilities (comma separated)"), { target: { value: "code generation, vision" } });
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Add model" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toBe("/api/v1/model-registry");
    expect(post.mock.calls[0][1]).toMatchObject({
      model_id: "openai/gpt-4o",
      provider_key_id: "k1",
      max_data_class: "confidential",
      regions: ["eu"],
      capabilities: ["CODE_GENERATION", "VISION"],
      enabled: true,
    });
  });

  it("refuses an add with no region or a malformed model before calling the API", async () => {
    route([]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Add model" }));
    fireEvent.change(screen.getByLabelText("Model"), { target: { value: "gpt-4o" } });
    fireEvent.submit(screen.getByLabelText("Model").closest("form")!);
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith(expect.stringContaining("provider/name"));
    fireEvent.change(screen.getByLabelText("Model"), { target: { value: "openai/gpt-4o" } });
    fireEvent.submit(screen.getByLabelText("Model").closest("form")!);
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith(expect.stringContaining("region"));
    expect(post).not.toHaveBeenCalled();
  });

  it("toggles enabled through the API", async () => {
    route([entry()]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Disable openai/gpt-4o" }));
    await waitFor(() => expect(patch).toHaveBeenCalledWith("/api/v1/model-registry/m1", { enabled: false }, "tok"));
  });

  it("edits an entry without letting the model id change", async () => {
    route([entry()]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Edit openai/gpt-4o" }));
    expect(screen.queryByLabelText("Model")).toBeNull();
    fireEvent.change(screen.getByLabelText("Risk rating"), { target: { value: "high" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    const [path, body] = patch.mock.calls[0];
    expect(path).toBe("/api/v1/model-registry/m1");
    expect(body).toMatchObject({ risk_rating: "high", regions: ["us"], max_data_class: "internal", provider_key_id: "k1" });
    expect("model_id" in (body as Record<string, unknown>)).toBe(false);
  });

  it("asks before removing, and removes only once confirmed", async () => {
    route([entry()]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Remove openai/gpt-4o" }));
    expect(del).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole("button", { name: "Remove model" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("/api/v1/model-registry/m1", "tok"));
  });
});
