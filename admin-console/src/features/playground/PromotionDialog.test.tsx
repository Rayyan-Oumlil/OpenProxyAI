import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PromotionStatus } from "../../api/evaluationTypes";
import type { PromptTemplate } from "../../api/types";
import { PromotionDialog } from "./PromotionDialog";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn(), post: vi.fn() } }));

import { toast } from "sonner";
import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);
const post = vi.mocked(apiClient.post);

const TEMPLATE = { id: "t2", name: "support", version: 2, status: "draft", user_template: "{{q}}", system_message: "Be brief." } as PromptTemplate;

function status(overrides: Partial<PromotionStatus> = {}): PromotionStatus {
  return {
    template_id: "t2", name: "support", version: 2, status: "draft", gate_enabled: true, requirements: { min_pass_rate: 0.8, min_items: 10 },
    passes_gate: false, qualifying_run: null, best_run: null, reasons: ["no eval run has tested this exact prompt; run one with prompt_template_id set, after your last edit"], ...overrides,
  };
}

const RUN = { run_id: "r1", status: "completed", total_items: 20, scored_items: 20, failed_items: 0, pass_rate: 0.9, mean_score: 0.9 };

function renderDialog(isAdmin = true, onClose = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PromotionDialog template={TEMPLATE} isAdmin={isAdmin} token="tok" onClose={onClose} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return onClose;
}

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  vi.mocked(toast.error).mockReset();
  vi.mocked(toast.success).mockReset();
});
afterEach(cleanup);

describe("PromotionDialog", () => {
  it("says what is missing and what the bar is, and keeps Promote disabled", async () => {
    get.mockResolvedValue(status());
    renderDialog();
    expect(await screen.findByText(/Not ready/)).toBeTruthy();
    expect(screen.getByText(/pass at 80% over at least 10 scored items/)).toBeTruthy();
    expect(screen.getByText(/no eval run has tested this exact prompt/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Promote" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("link", { name: "Run an eval of this prompt" }).getAttribute("href")).toBe("/eval-runs?template=t2");
  });

  it("shows the closest run when one exists", async () => {
    get.mockResolvedValue(status({ best_run: { ...RUN, pass_rate: 0.6 }, reasons: ["the pass rate was 60%; at least 80% is required"] }));
    renderDialog();
    expect(await screen.findByText(/Closest run: 20 of 20 items scored, 60% passed \(completed\)/)).toBeTruthy();
  });

  it("promotes when a run vouches for it", async () => {
    get.mockResolvedValue(status({ passes_gate: true, qualifying_run: RUN, reasons: [] }));
    post.mockResolvedValue({ template_id: "t2", name: "support", version: 2, status: "active", previous_version: 1, run_id: "r1", overridden: false });
    const onClose = renderDialog();
    expect(await screen.findByText(/An eval run vouches for this exact prompt: 20 of 20 items scored, 90% passed/)).toBeTruthy();
    expect(screen.queryByText("Override")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Promote" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/api/v1/prompt-templates/t2/promote", {}, "tok"));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(toast.success).toHaveBeenCalledWith("v2 is live.");
  });

  it("will not override without a written reason, then sends it", async () => {
    get.mockResolvedValue(status());
    post.mockResolvedValue({ template_id: "t2", name: "support", version: 2, status: "active", previous_version: 1, run_id: null, overridden: true });
    renderDialog();
    fireEvent.click(await screen.findByLabelText(/Promote anyway/));
    const button = screen.getByRole("button", { name: "Promote with override" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "too short" } });
    expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "Urgent customer-facing fix, run to follow" } });
    expect(button.disabled).toBe(false);
    fireEvent.click(button);
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/api/v1/prompt-templates/t2/promote", { override: true, reason: "Urgent customer-facing fix, run to follow" }, "tok"),
    );
    expect(toast.success).toHaveBeenCalledWith("v2 is live (override recorded).");
  });

  it("shows the server's explanation when promotion is refused", async () => {
    get.mockResolvedValue(status({ passes_gate: true, qualifying_run: RUN, reasons: [] }));
    post.mockRejectedValue(new Error("Only a draft can be promoted; this version is active."));
    renderDialog();
    await screen.findByText(/An eval run vouches/);
    fireEvent.click(screen.getByRole("button", { name: "Promote" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Only a draft can be promoted; this version is active."));
  });

  it("says the gate is off when it is, and lets the admin promote", async () => {
    get.mockResolvedValue(status({ gate_enabled: false, passes_gate: true, reasons: [] }));
    renderDialog();
    expect(await screen.findByText(/promotion gate is off/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Promote" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("lets a non-admin look but not promote", async () => {
    get.mockResolvedValue(status());
    renderDialog(false);
    expect(await screen.findByText(/Not ready/)).toBeTruthy();
    expect(screen.getByText("Only an admin can promote a prompt.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Promote" })).toBeNull();
    expect(screen.queryByLabelText(/Promote anyway/)).toBeNull();
  });

  it("reports a failure to load the status", async () => {
    get.mockRejectedValue(new Error("boom"));
    renderDialog();
    expect(await screen.findByText("boom")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Promote" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
