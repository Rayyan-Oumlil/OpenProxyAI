import { cleanup, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { RequestLogDetail } from "../../api/types";
import { RequestTracePage } from "./RequestTracePage";

vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ token: "tok" }) }));
vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn() } }));

import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);

function detail(overrides: Partial<RequestLogDetail> = {}): RequestLogDetail {
  return {
    id: "l1",
    created_at: "2026-11-03T10:00:00Z",
    model: "openai/gpt-4o-mini",
    provider: "openai",
    status: "success",
    prompt_tokens: 10,
    completion_tokens: 5,
    total_tokens: 15,
    cost_usd: 0.00001,
    latency_ms: 120,
    ttft_ms: null,
    error_message: null,
    policy_action: "allow",
    policy_reason: null,
    request_id: "req-123",
    user_id: "u1",
    api_key_id: "k1",
    request_metadata: {
      cache: "miss",
      stages: [
        { name: "auth", start_ms: 0, ms: 6 },
        { name: "policy", start_ms: 6, ms: 12 },
        { name: "rate_limit", start_ms: 18, ms: 3 },
        { name: "cache", start_ms: 21, ms: 4 },
        { name: "upstream", start_ms: 25, ms: 100 },
      ],
    },
    policy_triggered_rules: null,
    ...overrides,
  };
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/logs/l1"]}>
        <Routes>
          <Route path="/logs/:id" element={<RequestTracePage />} />
          <Route path="/logs" element={<h1>Logs list</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
});
afterEach(cleanup);

describe("RequestTracePage", () => {
  it("draws the recorded stages with their durations, in order", async () => {
    get.mockResolvedValue(detail());
    renderPage();
    const waterfall = await screen.findByRole("region", { name: "Where the time went" });
    const rows = within(waterfall).getAllByRole("listitem");
    expect(rows.map((r) => r.querySelector(".trace-row__label")?.textContent)).toEqual([
      "Authentication",
      "Policy checks",
      "Rate limit and budget",
      "Cache lookup",
      "Upstream call",
    ]);
    expect(within(rows[0]).getByText("6ms")).toBeTruthy(); // authentication is timed, not "not timed"
    expect(within(rows[1]).getByText("12ms")).toBeTruthy();
    expect(within(rows[4]).getByText("100ms")).toBeTruthy();
    expect(within(waterfall).queryByText("not timed")).toBeNull();
    expect(within(waterfall).getByText("Total 125ms")).toBeTruthy(); // the stages run past the logged latency, so they set the total
    expect(get).toHaveBeenCalledWith("/api/v1/analytics/logs/l1", "tok");
  });

  it("keeps the 'not timed' row for requests logged before authentication was timed", async () => {
    get.mockResolvedValue(detail({ request_metadata: { stages: [{ name: "policy", start_ms: 0, ms: 5 }, { name: "upstream", start_ms: 5, ms: 40 }] } }));
    renderPage();
    const waterfall = await screen.findByRole("region", { name: "Where the time went" });
    expect(within(waterfall).getByText("not timed")).toBeTruthy();
    expect(within(waterfall).getAllByText("Authentication")).toHaveLength(1);
  });

  it("shows how sensitive the request was judged to be and why, and omits it for older rows", async () => {
    get.mockResolvedValue(detail({ request_metadata: { data_class: { class: "confidential", source: "detected", entities: ["ssn"] } } }));
    renderPage();
    expect(await screen.findByText("Data class")).toBeTruthy();
    expect(screen.getByText("Confidential (detected: ssn)")).toBeTruthy();
    cleanup();
    get.mockResolvedValue(detail({ request_metadata: {} }));
    renderPage();
    await screen.findByText("What happened");
    expect(screen.queryByText("Data class")).toBeNull();
  });

  it("shows a policy block as blocked, with its reason, and says the upstream was not reached", async () => {
    get.mockResolvedValue(
      detail({
        status: "error",
        policy_action: "block",
        policy_reason: "blocked_keyword",
        policy_triggered_rules: ["project-phoenix"],
        error_message: "policy_blocked: blocked_keyword",
        request_metadata: { stages: [{ name: "policy", start_ms: 0, ms: 4 }] },
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: 0,
        cost_usd: 0,
      }),
    );
    renderPage();
    const outcome = await screen.findByRole("region", { name: "What happened" });
    expect(within(outcome).getByText("Blocked")).toBeTruthy();
    expect(within(outcome).getByText("blocked_keyword")).toBeTruthy();
    expect(within(outcome).getByText(/project-phoenix/)).toBeTruthy();
    expect(within(outcome).getByText("Not reached")).toBeTruthy();
    expect(within(outcome).getByText("Not consulted")).toBeTruthy();
    expect(screen.queryByText("Upstream call")).toBeNull();
  });

  it("reports a cache hit and no upstream stage", async () => {
    get.mockResolvedValue(
      detail({
        request_metadata: {
          cache: "l2",
          stages: [
            { name: "policy", start_ms: 0, ms: 2 },
            { name: "rate_limit", start_ms: 2, ms: 1 },
            { name: "cache", start_ms: 3, ms: 2 },
          ],
        },
      }),
    );
    renderPage();
    expect(await screen.findByText("Hit (l2)")).toBeTruthy();
    expect(screen.queryByText("Upstream call")).toBeNull();
  });

  it("says timings are unavailable for a row logged without stages, instead of drawing bars", async () => {
    get.mockResolvedValue(detail({ request_metadata: { cache: "miss" } }));
    renderPage();
    expect(await screen.findByText(/Stage timings are not available/)).toBeTruthy();
    expect(document.querySelector(".trace-row__bar")).toBeNull();
  });

  it("mentions fallbacks when the upstream needed them", async () => {
    get.mockResolvedValue(detail({ request_metadata: { fallback_count: 2, fallback_model_used: "openai/gpt-4o", stages: [{ name: "upstream", start_ms: 0, ms: 50 }] } }));
    renderPage();
    expect(await screen.findByText(/2 fallbacks \(to openai\/gpt-4o\)/)).toBeTruthy();
  });

  it("shows an error state when the request cannot be loaded", async () => {
    get.mockRejectedValue(new Error("Log entry not found"));
    renderPage();
    expect(await screen.findByText("Unable to load this request")).toBeTruthy();
    expect(screen.getByText("Log entry not found")).toBeTruthy();
  });

  it("links back to the request logs", async () => {
    get.mockResolvedValue(detail());
    renderPage();
    const link = await screen.findByRole("link", { name: /Request logs/ });
    expect(link.getAttribute("href")).toBe("/logs");
  });
});
