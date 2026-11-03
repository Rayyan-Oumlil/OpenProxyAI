import { cleanup, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ProviderKeyResponse } from "../../api/types";
import { ProviderHealthPage } from "./ProviderHealthPage";

vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ token: "tok" }) }));
vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn() } }));

import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);

function key(overrides: Partial<ProviderKeyResponse> = {}): ProviderKeyResponse {
  return {
    id: "k1",
    provider: "openai",
    alias: null,
    key_alias: "primary",
    key_prefix: "sk-abc123…",
    weight: 1,
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
      <MemoryRouter>
        <ProviderHealthPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
});
afterEach(cleanup);

describe("ProviderHealthPage", () => {
  it("shows each key's state with the reason and its measurements", async () => {
    get.mockResolvedValue([
      key({ id: "a", key_alias: "primary", health_status: "healthy", last_health_check_at: "2026-11-03T10:00:00Z", latency_p99_ms: 840, error_rate: 0.02, weight: 5, effective_weight: 3 }),
      key({ id: "b", key_alias: "backup", provider: "anthropic", health_status: "unhealthy", consecutive_failures: 3, last_health_check_at: "2026-11-03T10:00:00Z" }),
    ]);
    renderPage();

    await screen.findByText("5 (effective 3)"); // rows are in; the table first renders as a skeleton
    const table = screen.getByRole("table", { name: "Provider key health" });
    const [, primary, backup] = within(table).getAllByRole("row");
    expect(within(primary).getByText("Healthy")).toBeTruthy();
    expect(within(primary).getByText("840ms")).toBeTruthy();
    expect(within(primary).getByText("2.0%")).toBeTruthy();
    expect(within(primary).getByText("5 (effective 3)")).toBeTruthy();
    expect(within(backup).getByText("Down")).toBeTruthy();
    expect(within(backup).getByText(/Failed 3 health checks in a row/)).toBeTruthy();
  });

  it("summarises keys per state", async () => {
    get.mockResolvedValue([key({ id: "a", health_status: "healthy" }), key({ id: "b", health_status: "healthy" }), key({ id: "c", is_active: false })]);
    renderPage();
    const summary = await screen.findByRole("list", { name: "Keys by state" });
    const items = within(summary).getAllByRole("listitem").map((li) => li.textContent);
    expect(items).toContain("2Healthy");
    expect(items).toContain("1Disabled");
  });

  it("says why data is missing instead of showing healthy-looking blanks", async () => {
    get.mockResolvedValue([key()]);
    renderPage();
    expect(await screen.findByText(/No health check has run yet/)).toBeTruthy();
    expect(screen.getByText(/No latency or error data/)).toBeTruthy();
    const row = within(screen.getByRole("table", { name: "Provider key health" })).getAllByRole("row")[1];
    expect(within(row).getByText("Not checked")).toBeTruthy();
    expect(within(row).getByText("Never")).toBeTruthy();
  });

  it("shows the empty state with no keys", async () => {
    get.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("No provider keys")).toBeTruthy();
    expect(screen.queryByRole("list", { name: "Keys by state" })).toBeNull();
  });

  it("shows an error with retry when the list fails", async () => {
    get.mockRejectedValue(new Error("boom"));
    renderPage();
    expect(await screen.findByText("Unable to load provider health")).toBeTruthy();
    expect(screen.getByText("boom")).toBeTruthy();
    expect(screen.getByText("Try again")).toBeTruthy();
  });
});
