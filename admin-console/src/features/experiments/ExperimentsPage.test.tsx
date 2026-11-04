import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ExperimentResponse } from "../../api/types";
import { ConfirmProvider } from "../../components/ui/ConfirmDialog";
import { ExperimentsPage } from "./ExperimentsPage";

vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ token: "tok", user: { role: "admin" } }) }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("../../api/client", () => ({
  apiClient: {
    getExperiments: vi.fn(),
    createExperiment: vi.fn(),
    updateExperiment: vi.fn(),
    startExperiment: vi.fn(),
    stopExperiment: vi.fn(),
    deleteExperiment: vi.fn(),
    getExperimentResults: vi.fn(),
  },
}));

import { apiClient } from "../../api/client";

const api = vi.mocked(apiClient);

function experiment(overrides: Partial<ExperimentResponse> = {}): ExperimentResponse {
  return {
    id: "e1",
    name: "mini-vs-4o",
    target_model: "gpt-4o",
    is_active: false,
    created_at: "2026-11-01T10:00:00Z",
    variants: [
      { model: "gpt-4o", traffic_weight: 50 },
      { model: "gpt-4o-mini", traffic_weight: 50 },
    ],
    ...overrides,
  } as ExperimentResponse;
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ConfirmProvider>
        <ExperimentsPage />
      </ConfirmProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  Object.values(api).forEach((fn) => fn.mockReset());
  api.startExperiment.mockResolvedValue(experiment({ is_active: true }));
  api.stopExperiment.mockResolvedValue(experiment());
  api.deleteExperiment.mockResolvedValue(undefined);
});
afterEach(cleanup);

describe("ExperimentsPage", () => {
  it("lists experiments with target model, variants and status", async () => {
    api.getExperiments.mockResolvedValue([experiment(), experiment({ id: "e2", name: "live-one", is_active: true })]);
    renderPage();
    await screen.findByText("mini-vs-4o");
    expect(screen.getAllByText("gpt-4o (50), gpt-4o-mini (50)")).toHaveLength(2);
    expect(screen.getByText("Active")).toBeTruthy();
    expect(screen.getByText("Inactive")).toBeTruthy();
  });

  it("starts an inactive experiment and stops an active one", async () => {
    api.getExperiments.mockResolvedValue([experiment(), experiment({ id: "e2", name: "live-one", is_active: true })]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Start experiment mini-vs-4o" }));
    await waitFor(() => expect(api.startExperiment).toHaveBeenCalledWith("e1", "tok"));
    fireEvent.click(screen.getByRole("button", { name: "Stop experiment live-one" }));
    await waitFor(() => expect(api.stopExperiment).toHaveBeenCalledWith("e2", "tok"));
  });

  it("asks before deleting, and deletes only once confirmed", async () => {
    api.getExperiments.mockResolvedValue([experiment()]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Delete experiment mini-vs-4o" }));
    expect(await screen.findByRole("dialog", { name: "Delete experiment?" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.deleteExperiment).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Delete experiment mini-vs-4o" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete experiment" }));
    await waitFor(() => expect(api.deleteExperiment).toHaveBeenCalledWith("e1", "tok"));
  });

  it("loads results only when asked", async () => {
    api.getExperiments.mockResolvedValue([experiment()]);
    api.getExperimentResults.mockRejectedValue(new Error("no data yet"));
    renderPage();
    await screen.findByText("mini-vs-4o");
    expect(api.getExperimentResults).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "View results" }));
    await waitFor(() => expect(api.getExperimentResults).toHaveBeenCalledWith("e1", "tok"));
  });

  it("keeps the header and the new-experiment button when loading fails, with a retry", async () => {
    api.getExperiments.mockRejectedValue(new Error("boom"));
    renderPage();
    expect(await screen.findByText("Unable to load experiments")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Experiments" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Create new experiment" })).toBeTruthy();
    expect(screen.getByText("Try again")).toBeTruthy();
  });

  it("shows the empty state", async () => {
    api.getExperiments.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("No experiments")).toBeTruthy();
  });
});
