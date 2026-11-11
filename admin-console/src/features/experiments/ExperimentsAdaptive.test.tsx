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

import { toast } from "sonner";
import { apiClient } from "../../api/client";

const api = vi.mocked(apiClient);

function experiment(overrides: Partial<ExperimentResponse> = {}): ExperimentResponse {
  return {
    id: "e1",
    org_id: "o1",
    name: "mini-vs-4o",
    target_model: "gpt-4o",
    is_active: true,
    created_at: "2026-11-01T10:00:00Z",
    variants: [
      { id: "v1", experiment_id: "e1", model: "gpt-4o", traffic_weight: 50 },
      { id: "v2", experiment_id: "e1", model: "gpt-4o-mini", traffic_weight: 50 },
    ],
    ...overrides,
  } as ExperimentResponse;
}

const ADAPTIVE = { mode: "adaptive", metric: "thumbs", min_samples_per_variant: 30, delta: 0.01, weight_floor: 5 } as const;

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

const resultRow = (id: string, model: string, weight: number, chance: number) => ({
  variant_id: id,
  model,
  traffic_weight: weight,
  probability_best: chance,
  request_count: 3,
  avg_latency_ms: 10,
  total_cost_usd: 0,
  total_prompt_tokens: 1,
  total_completion_tokens: 1,
  policy_violations: 0,
});

const adaptiveStatus = (overrides = {}) => ({
  metric: "thumbs", ready: false, min_samples_per_variant: 30, delta: 0.01, samples: {}, winner_variant_id: null, stopped_reason: null, error: null, ...overrides,
});

beforeEach(() => {
  Object.values(api).forEach((fn) => fn.mockReset());
  vi.mocked(toast.error).mockReset();
  api.startExperiment.mockResolvedValue(experiment());
});
afterEach(cleanup);

describe("ExperimentsPage, adaptive tests", () => {
  it("creates an adaptive experiment with its settings, and refuses one with a single variant", async () => {
    api.getExperiments.mockResolvedValue([]);
    api.createExperiment.mockResolvedValue(experiment());
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Create new experiment" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "mini vs full" } });
    fireEvent.change(screen.getByLabelText(/Target model/), { target: { value: "openai/gpt-4o" } });
    fireEvent.change(screen.getByLabelText("Variant 1 model"), { target: { value: "openai/gpt-4o-mini" } });
    fireEvent.click(screen.getByLabelText(/Adaptive\./));
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(toast.error).toHaveBeenCalledWith("An adaptive experiment compares variants, so it needs at least two.");
    expect(api.createExperiment).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Add variant" }));
    fireEvent.change(screen.getByLabelText("Variant 2 model"), { target: { value: "openai/gpt-4o" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() =>
      expect(api.createExperiment).toHaveBeenCalledWith(
        {
          name: "mini vs full",
          target_model: "openai/gpt-4o",
          ...ADAPTIVE,
          variants: [
            { model: "openai/gpt-4o-mini", traffic_weight: 50 },
            { model: "openai/gpt-4o", traffic_weight: 50 },
          ],
        },
        "tok",
      ),
    );
  });

  it("holds an adaptive test to at least 20 ratings per variant", async () => {
    api.getExperiments.mockResolvedValue([]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Create new experiment" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "x" } });
    fireEvent.change(screen.getByLabelText(/Target model/), { target: { value: "m/a" } });
    fireEvent.change(screen.getByLabelText("Variant 1 model"), { target: { value: "m/b" } });
    fireEvent.click(screen.getByRole("button", { name: "Add variant" }));
    fireEvent.change(screen.getByLabelText("Variant 2 model"), { target: { value: "m/c" } });
    fireEvent.click(screen.getByLabelText(/Adaptive\./));
    const minimum = screen.getByLabelText(/Ratings needed per variant/) as HTMLInputElement;
    fireEvent.change(minimum, { target: { value: "5" } });
    // The field's own min stops the submit with the browser's message before the handler runs; either way nothing is sent.
    expect(minimum.validity.rangeUnderflow).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(api.createExperiment).not.toHaveBeenCalled();
  });

  it("editing only the name does not resend the variants, which would replace them and the ratings", async () => {
    api.getExperiments.mockResolvedValue([experiment(ADAPTIVE)]);
    api.updateExperiment.mockResolvedValue(experiment());
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Edit experiment mini-vs-4o" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "renamed" } });
    fireEvent.click(screen.getByRole("button", { name: "Update" }));
    await waitFor(() => expect(api.updateExperiment).toHaveBeenCalledTimes(1));
    const [, body] = api.updateExperiment.mock.calls[0];
    expect(body).toEqual({ name: "renamed", ...ADAPTIVE });
    expect(body).not.toHaveProperty("variants");
  });

  it("warns, and does send the variants, when they are changed on an adaptive test", async () => {
    api.getExperiments.mockResolvedValue([experiment(ADAPTIVE)]);
    api.updateExperiment.mockResolvedValue(experiment());
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Edit experiment mini-vs-4o" }));
    expect(screen.queryByText(/replaces them, so ratings collected so far/)).toBeNull();
    fireEvent.change(screen.getByLabelText("Variant 2 model"), { target: { value: "gpt-4.1" } });
    expect(screen.getByText(/replaces them, so ratings collected so far/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Update" }));
    await waitFor(() => expect(api.updateExperiment).toHaveBeenCalledTimes(1));
    expect(api.updateExperiment.mock.calls[0][1].variants).toEqual([
      { model: "gpt-4o", traffic_weight: 50 },
      { model: "gpt-4.1", traffic_weight: 50 },
    ]);
  });

  it("shows the adaptive badge and the winner", async () => {
    api.getExperiments.mockResolvedValue([
      experiment({
        ...ADAPTIVE,
        is_active: false,
        winner_variant_id: "v2",
        stopped_reason: "winner",
        variants: [
          { id: "v1", model: "gpt-4o", traffic_weight: 20 },
          { id: "v2", model: "gpt-4o-mini", traffic_weight: 80 },
        ] as ExperimentResponse["variants"],
      }),
    ]);
    renderPage();
    expect(await screen.findByText("Adaptive")).toBeTruthy();
    expect(screen.getByText("Winner: gpt-4o-mini")).toBeTruthy();
  });

  it("flags an adaptive test the job could not update", async () => {
    api.getExperiments.mockResolvedValue([experiment({ ...ADAPTIVE, adaptive_error: "metric 'thumbs' has values outside 0 to 1" })]);
    renderPage();
    expect(await screen.findByText("Needs attention")).toBeTruthy();
  });

  it("explains that nothing moves yet while ratings are still being collected", async () => {
    api.getExperiments.mockResolvedValue([experiment(ADAPTIVE)]);
    api.getExperimentResults.mockResolvedValue({
      variants: [resultRow("v1", "gpt-4o", 50, 0.4)],
      adaptive: adaptiveStatus({ samples: { v1: 22, v2: 7 } }),
    });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /Show details for mini-vs-4o results/ }));
    expect(await screen.findByText(/Collecting ratings: gpt-4o 22, gpt-4o-mini 7 of 30 each/)).toBeTruthy();
    expect(screen.getByText(/Nothing moves until every variant has enough \(23 more for the slowest\)/)).toBeTruthy();
    expect(screen.getByText("40%")).toBeTruthy();
  });

  it("says the winner is recorded and not deployed", async () => {
    api.getExperiments.mockResolvedValue([
      experiment({
        ...ADAPTIVE,
        is_active: false,
        winner_variant_id: "v2",
        stopped_reason: "winner",
        variants: [
          { id: "v1", model: "gpt-4o-mini", traffic_weight: 5 },
          { id: "v2", model: "gpt-4o", traffic_weight: 95 },
        ] as ExperimentResponse["variants"],
      }),
    ]);
    api.getExperimentResults.mockResolvedValue({
      variants: [],
      adaptive: adaptiveStatus({ ready: true, samples: { v1: 40, v2: 41 }, winner_variant_id: "v2", stopped_reason: "winner" }),
    });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /Show details for mini-vs-4o results/ }));
    expect(await screen.findByText(/This is recorded, not deployed/)).toBeTruthy();
  });

  it("lists two variants on the same model as two rows", async () => {
    api.getExperiments.mockResolvedValue([experiment(ADAPTIVE)]);
    api.getExperimentResults.mockResolvedValue({
      variants: [resultRow("v1", "gpt-4o-mini", 30, 0.2), resultRow("v2", "gpt-4o-mini", 70, 0.8)],
      adaptive: adaptiveStatus(),
    });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /Show details for mini-vs-4o results/ }));
    expect(await screen.findAllByText("gpt-4o-mini")).toHaveLength(2);
    expect(screen.getByText("30%")).toBeTruthy();
    expect(screen.getByText("70%")).toBeTruthy();
  });

  it("opens the results in a full-width row, and pressing a control in the row does not toggle it", async () => {
    api.getExperiments.mockResolvedValue([experiment(ADAPTIVE)]);
    api.getExperimentResults.mockResolvedValue({ variants: [], adaptive: adaptiveStatus() });
    renderPage();
    const toggle = await screen.findByRole("button", { name: /Show details for mini-vs-4o results/ });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(screen.getByRole("button", { name: "Edit experiment mini-vs-4o" }));
    expect(api.getExperimentResults).not.toHaveBeenCalled(); // Edit opened its dialog, not the results
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    fireEvent.click(toggle);
    await waitFor(() => expect(api.getExperimentResults).toHaveBeenCalledWith("e1", "tok"));
    expect(screen.getByRole("button", { name: /Hide details for mini-vs-4o results/ }).getAttribute("aria-expanded")).toBe("true");
  });

  it("asks before starting a stopped test again, because that clears its winner", async () => {
    api.getExperiments.mockResolvedValue([
      experiment({
        ...ADAPTIVE,
        is_active: false,
        winner_variant_id: "v2",
        variants: [
          { id: "v1", model: "a", traffic_weight: 5 },
          { id: "v2", model: "b", traffic_weight: 95 },
        ] as ExperimentResponse["variants"],
      }),
    ]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Start experiment mini-vs-4o" }));
    expect(api.startExperiment).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole("button", { name: "Start again" }));
    await waitFor(() => expect(api.startExperiment).toHaveBeenCalledWith("e1", "tok"));
  });
});
