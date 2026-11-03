import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { OrganizationResponse } from "../../api/types";
import { OrganizationSettingsPage } from "./OrganizationSettingsPage";

vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ token: "tok", user: { role: "admin" } }) }));
vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn(), patch: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);

function org(overrides: Partial<OrganizationResponse> = {}): OrganizationResponse {
  return {
    id: "o1",
    name: "Demo Org",
    slug: "demo",
    plan: "starter",
    settings: { policy: { enforcement_mode: "enforce" } },
    budget_monthly_usd: "100",
    is_active: true,
    data_region: "eu",
    created_at: "2026-11-01T10:00:00Z",
    ...overrides,
  };
}

function renderPage(client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <OrganizationSettingsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

beforeEach(() => {
  get.mockReset();
});
afterEach(cleanup);

describe("OrganizationSettingsPage", () => {
  it("fills the form from the loaded organization", async () => {
    get.mockResolvedValue(org());
    renderPage();

    expect(await screen.findByDisplayValue("Demo Org")).toBeTruthy();
    expect((screen.getByLabelText("Monthly budget (USD)") as HTMLInputElement).value).toBe("100");
    expect((screen.getByLabelText("Data Region") as HTMLSelectElement).value).toBe("eu");
    expect((screen.getByLabelText(/Settings/i) as HTMLTextAreaElement).value).toContain("enforcement_mode");
  });

  it("keeps what the person typed until the organization data actually changes", async () => {
    get.mockResolvedValue(org());
    renderPage();
    const name = (await screen.findByDisplayValue("Demo Org")) as HTMLInputElement;

    fireEvent.change(name, { target: { value: "Renamed locally" } });
    expect(name.value).toBe("Renamed locally"); // re-rendering must not overwrite the edit
  });

  it("refills the form when a refetch returns a changed organization", async () => {
    get.mockResolvedValue(org());
    const client = renderPage();
    await screen.findByDisplayValue("Demo Org");

    get.mockResolvedValue(org({ name: "Renamed on the server", budget_monthly_usd: "250" }));
    await client.invalidateQueries({ queryKey: ["organization", "current"] });

    await waitFor(() => expect(screen.getByDisplayValue("Renamed on the server")).toBeTruthy());
    expect((screen.getByLabelText("Monthly budget (USD)") as HTMLInputElement).value).toBe("250");
  });

  it("shows an error when the organization cannot be loaded", async () => {
    get.mockRejectedValue(new Error("nope"));
    renderPage();
    expect(await screen.findByText(/nope/)).toBeTruthy();
  });
});
