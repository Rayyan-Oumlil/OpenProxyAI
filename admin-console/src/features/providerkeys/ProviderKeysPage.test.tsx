import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ProviderKeyResponse } from "../../api/types";
import { ConfirmProvider } from "../../components/ui/ConfirmDialog";
import { ProviderKeysPage } from "./ProviderKeysPage";

vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ token: "tok", user: { role: "admin" } }) }));
vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);
const patch = vi.mocked(apiClient.patch);
const del = vi.mocked(apiClient.del);

function key(overrides: Partial<ProviderKeyResponse> = {}): ProviderKeyResponse {
  return {
    id: "k1",
    provider: "openai",
    alias: null,
    key_alias: "primary",
    key_prefix: "sk-abc123",
    weight: 3,
    is_active: true,
    region: "us",
    model_patterns: null,
    created_at: "2026-11-01T10:00:00Z",
    ...overrides,
  };
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ConfirmProvider>
        <ProviderKeysPage />
      </ConfirmProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  patch.mockReset();
  del.mockReset();
  patch.mockResolvedValue(key());
  del.mockResolvedValue(undefined);
});
afterEach(cleanup);

describe("ProviderKeysPage", () => {
  it("lists keys with provider, alias, region, masked prefix and status", async () => {
    get.mockResolvedValue([key(), key({ id: "k2", key_alias: "eu-backup", provider: "anthropic", region: "eu", is_active: false })]);
    renderPage();
    const table = await screen.findByRole("table", { name: "Provider keys" });
    await within(table).findByText("eu-backup");
    expect(within(table).getByText("EU")).toBeTruthy();
    expect(within(table).getAllByText("sk-abc123…")).toHaveLength(2);
    expect(within(table).getByText("Inactive")).toBeTruthy();
  });

  it("shows the adaptive columns only when a key reports them", async () => {
    get.mockResolvedValue([key()]);
    const { unmount } = renderPage();
    await screen.findByText("primary");
    expect(screen.queryByText("P99 (ms)")).toBeNull();
    unmount();

    get.mockResolvedValue([key({ latency_p99_ms: 840.4, error_rate: 0.025, effective_weight: 2 })]);
    renderPage();
    expect(await screen.findByText("P99 (ms)")).toBeTruthy();
    expect(screen.getByText("840")).toBeTruthy();
    expect(screen.getByText("2.5%")).toBeTruthy();
  });

  it("marks a key whose circuit is open, and not one whose circuit has expired", async () => {
    const future = Date.now() / 1000 + 3600;
    const past = Date.now() / 1000 - 3600;
    get.mockResolvedValue([key({ id: "a", key_alias: "tripped", circuit_open_until: future }), key({ id: "b", key_alias: "recovered", circuit_open_until: past })]);
    renderPage();
    await screen.findByText("tripped");
    expect(screen.getAllByText("Open")).toHaveLength(1);
    expect(screen.getAllByText("Closed")).toHaveLength(1);
  });

  it("filters by region and explains an empty result", async () => {
    get.mockResolvedValue([key(), key({ id: "k2", key_alias: "eu-backup", region: "eu" })]);
    renderPage();
    await screen.findByText("eu-backup");
    fireEvent.change(screen.getByLabelText("Filter provider keys by region"), { target: { value: "ap" } });
    expect(await screen.findByText("No keys in this region")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Filter provider keys by region"), { target: { value: "eu" } });
    expect(await screen.findByText("eu-backup")).toBeTruthy();
    expect(screen.queryByText("primary")).toBeNull();
  });

  it("deactivates a key through the API", async () => {
    get.mockResolvedValue([key()]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Deactivate primary" }));
    await waitFor(() => expect(patch).toHaveBeenCalledWith("/api/v1/provider-keys/k1", { is_active: false }, "tok"));
  });

  it("asks before deleting, and deletes only once confirmed", async () => {
    get.mockResolvedValue([key()]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Delete primary" }));
    fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(del).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Delete primary" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete key" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("/api/v1/provider-keys/k1", "tok"));
  });

  it("keeps the header and the add button when loading fails, with a retry", async () => {
    get.mockRejectedValue(new Error("boom"));
    renderPage();
    expect(await screen.findByText("Unable to load provider keys")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Provider keys" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add provider key" })).toBeTruthy();
    expect(screen.getByText("Try again")).toBeTruthy();
  });

  it("shows the empty state, with the add button still available", async () => {
    get.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("No provider keys")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add provider key" })).toBeTruthy();
  });
});
