import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { EvalRun, EvalRunItem } from "../../api/evaluationTypes";
import { ConfirmProvider } from "../../components/ui/ConfirmDialog";
import { EvalRunsPage } from "./EvalRunsPage";

const auth = vi.hoisted(() => ({ role: "admin" }));
vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ token: "tok", user: { role: auth.role } }) }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), del: vi.fn(), getPromptTemplates: vi.fn() } }));

import { toast } from "sonner";
import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);
const post = vi.mocked(apiClient.post);

function run(overrides: Partial<EvalRun> = {}): EvalRun {
  return {
    id: "r1", dataset_id: "d1", evaluator_id: "e1", evaluator: { name: "exact-match", type: "exact", config: {} }, prompt_template_id: null,
    candidate_model: "openai/gpt-4o-mini", status: "completed", total_items: 20, completed_items: 20, scored_items: 18, failed_items: 2,
    passed_items: 15, mean_score: 0.8333, pass_rate: 15 / 18, cost_usd: 0.12, max_cost_usd: 1, error: null,
    created_at: "2026-11-01T10:00:00Z", started_at: "2026-11-01T10:00:01Z", finished_at: "2026-11-01T10:00:41Z", ...overrides,
  };
}

const ITEMS: EvalRunItem[] = [
  { id: "a", dataset_item_id: "i1", output: "Paris", score: 1, passed: true, reason: "matches the expected answer", error: null, cost_usd: 0.001, latency_ms: 10 },
  { id: "b", dataset_item_id: "i2", output: "Lyon", score: 0, passed: false, reason: "expected 'Paris', got 'Lyon'", error: null, cost_usd: 0.001, latency_ms: 10 },
  { id: "c", dataset_item_id: "i3", output: null, score: null, passed: null, reason: null, error: "Blocked by policy.", cost_usd: 0, latency_ms: 1 },
];

function mockApi(runs: EvalRun[]) {
  get.mockImplementation(async (path: string) => {
    if (path.startsWith("/api/v1/eval-runs/r1/items")) return ITEMS;
    if (path.startsWith("/api/v1/eval-runs")) return runs;
    if (path === "/api/v1/datasets") return [{ id: "d1", name: "support", description: null, item_count: 20, created_at: "2026-11-01T10:00:00Z" }];
    if (path === "/api/v1/evaluators") return [{ id: "e1", name: "exact-match", type: "exact", config: {}, created_at: "2026-11-01T10:00:00Z" }];
    throw new Error(`unmocked ${path}`);
  });
  vi.mocked(apiClient.getPromptTemplates).mockResolvedValue([]);
}

function renderPage(url = "/eval-runs") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <ConfirmProvider>
          <EvalRunsPage />
        </ConfirmProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  vi.mocked(toast.error).mockReset();
  auth.role = "admin";
});
afterEach(cleanup);

describe("EvalRunsPage", () => {
  it("lists runs with status, progress, pass rate and cost against the cap", async () => {
    mockApi([run()]);
    renderPage();
    expect(await screen.findByText("Completed")).toBeTruthy();
    expect(screen.getByText("20 / 20")).toBeTruthy();
    expect(screen.getByText("83%")).toBeTruthy();
    expect(screen.getByText("$0.12 of $1.00")).toBeTruthy();
  });

  it("shows a dash, not 0%, for a run that has no pass rate", async () => {
    mockApi([run({ status: "failed", scored_items: 0, passed_items: 0, pass_rate: null, mean_score: null })]);
    renderPage();
    await screen.findByText("Failed");
    expect(screen.queryByText("0%")).toBeNull();
  });

  it("is admin only", () => {
    auth.role = "developer";
    mockApi([]);
    renderPage();
    expect(screen.getByText(/You need admin privileges/)).toBeTruthy();
    expect(get).not.toHaveBeenCalled();
  });

  it("opens a run to show each item's result and explains the ones that could not be scored", async () => {
    mockApi([run()]);
    renderPage();
    fireEvent.click(await screen.findByText("openai/gpt-4o-mini"));
    expect(await screen.findByText("Paris")).toBeTruthy();
    expect(screen.getByText("Passed", { selector: "span" })).toBeTruthy();
    expect(screen.getByText("Failed", { selector: "span" })).toBeTruthy();
    expect(screen.getByText("Not scored", { selector: "span" })).toBeTruthy();
    expect(screen.getByText("Blocked by policy.")).toBeTruthy();
    expect(screen.getByText(/left out of the pass rate rather than counted as failures/)).toBeTruthy();
  });

  it("filters the items by outcome", async () => {
    mockApi([run()]);
    renderPage();
    fireEvent.click(await screen.findByText("openai/gpt-4o-mini"));
    await screen.findByText("Paris");
    fireEvent.change(screen.getByLabelText("Show"), { target: { value: "error" } });
    await waitFor(() => expect(get).toHaveBeenCalledWith("/api/v1/eval-runs/r1/items?limit=50&offset=0&outcome=error", "tok"));
  });

  it("offers cancel only for a run that is still going, and asks first", async () => {
    mockApi([run({ id: "r1", status: "running", completed_items: 5 }), run({ id: "r2", status: "completed" })]);
    post.mockResolvedValue(run({ status: "cancelled" }));
    renderPage();
    const cancel = await screen.findByRole("button", { name: "Cancel the run of openai/gpt-4o-mini" });
    expect(screen.getAllByRole("button", { name: /Cancel the run/ })).toHaveLength(1);
    fireEvent.click(cancel);
    expect(post).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole("button", { name: "Cancel run" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/api/v1/eval-runs/r1/cancel", {}, "tok"));
  });

  it("starts a run with the chosen dataset, evaluator, model and cap", async () => {
    mockApi([]);
    post.mockResolvedValue(run({ status: "queued" }));
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /Start a run/ }));
    await screen.findByRole("option", { name: "support (20 items)" });
    fireEvent.change(screen.getByLabelText("Dataset"), { target: { value: "d1" } });
    fireEvent.change(screen.getByLabelText("Evaluator"), { target: { value: "e1" } });
    fireEvent.change(screen.getByLabelText("Model to test"), { target: { value: "openai/gpt-4o-mini" } });
    fireEvent.change(screen.getByLabelText(/Cost cap/), { target: { value: "2.5" } });
    fireEvent.click(screen.getByRole("button", { name: "Start run" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/api/v1/eval-runs", { dataset_id: "d1", evaluator_id: "e1", candidate_model: "openai/gpt-4o-mini", max_items: 100, max_cost_usd: 2.5 }, "tok"),
    );
  });

  it("checks the form before calling the server", async () => {
    mockApi([]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /Start a run/ }));
    fireEvent.click(screen.getByRole("button", { name: "Start run" }));
    expect(toast.error).toHaveBeenLastCalledWith("Choose a dataset.");
    await screen.findByRole("option", { name: "support (20 items)" });
    fireEvent.change(screen.getByLabelText("Dataset"), { target: { value: "d1" } });
    fireEvent.change(screen.getByLabelText("Evaluator"), { target: { value: "e1" } });
    fireEvent.change(screen.getByLabelText("Model to test"), { target: { value: "gpt-4o" } });
    fireEvent.click(screen.getByRole("button", { name: "Start run" }));
    expect(toast.error).toHaveBeenLastCalledWith(expect.stringContaining("provider/name"));
    expect(post).not.toHaveBeenCalled();
  });

  it("shows the server's reason when a run is refused, for example the model is not on the allowlist", async () => {
    mockApi([]);
    post.mockRejectedValue(new Error("openai/gpt-4o is not on this organization's model allowlist"));
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /Start a run/ }));
    await screen.findByRole("option", { name: "support (20 items)" });
    fireEvent.change(screen.getByLabelText("Dataset"), { target: { value: "d1" } });
    fireEvent.change(screen.getByLabelText("Evaluator"), { target: { value: "e1" } });
    fireEvent.change(screen.getByLabelText("Model to test"), { target: { value: "openai/gpt-4o" } });
    fireEvent.click(screen.getByRole("button", { name: "Start run" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("openai/gpt-4o is not on this organization's model allowlist"));
  });

  it("opens the start form with the draft prompt chosen when arriving from the promotion dialog", async () => {
    mockApi([]);
    vi.mocked(apiClient.getPromptTemplates).mockResolvedValue([{ id: "t2", name: "support", version: 2, status: "draft" } as never]);
    renderPage("/eval-runs?template=t2");
    expect(await screen.findByRole("dialog", { name: "Start an eval run" })).toBeTruthy();
    await screen.findByRole("option", { name: "support v2 (draft)" });
    expect((screen.getByLabelText("Prompt template (optional)") as HTMLSelectElement).value).toBe("t2");
  });
});
