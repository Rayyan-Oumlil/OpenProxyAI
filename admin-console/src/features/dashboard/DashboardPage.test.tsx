import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AnalyticsResponse } from "../../api/types";
import { DashboardPage } from "./DashboardPage";
import { shiftDay } from "./metrics";

const auth = vi.hoisted(() => ({ role: "admin" }));
vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ token: "tok", user: { role: auth.role } }) }));
vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn(), getBlob: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("../../components/charts/DailyTrendChart", () => ({ DailyTrendChart: () => <div>trend chart</div> }));
vi.mock("../../components/charts/TopModelsChart", () => ({ TopModelsChart: () => <div>models chart</div> }));

import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);

const END = "2026-11-10";

function days(count: number, perDay: { requests: number; cost: number }, endIso = END) {
  return Array.from({ length: count }, (_, i) => ({
    date: shiftDay(endIso, i - (count - 1)),
    requests: perDay.requests,
    tokens: perDay.requests * 15,
    cost_usd: perDay.cost,
    avg_latency_ms: 100,
  }));
}

function overview(trend: ReturnType<typeof days>, overrides: Partial<AnalyticsResponse["overview"]> = {}): AnalyticsResponse {
  return {
    overview: {
      period_days: 30,
      total_requests: 600,
      successful_requests: 590,
      failed_requests: 10,
      policy_blocked_requests: 4,
      policy_flagged_requests: 2,
      total_tokens: 9000,
      total_cost_usd: 60,
      avg_latency_ms: 100,
      avg_ttft_ms: 40,
      p50_latency_ms: 90,
      p95_latency_ms: 300,
      p99_latency_ms: 400,
      projected_month_end_cost_usd: 180,
      forecast_basis_days: 10,
      cache_hit_rate: 0.25,
      ...overrides,
    },
    by_model: [{ model: "openai/gpt-4o-mini", provider: "openai", requests: 600, tokens: 9000, cost_usd: 60 }],
    by_user: [{ user_id: "u1", email: "ada@example.com", requests: 600, tokens: 9000, cost_usd: 60 }],
    by_team: [{ team_id: "t1", name: "Platform", requests: 600, tokens: 9000, cost_usd: 60 }],
    daily_trend: trend,
    generated_at: `${END}T12:00:00+00:00`,
  } as AnalyticsResponse;
}

/** Answers each analytics window by its period_days, the way the backend does. */
function mockApi({ budget = "100" as string | null, failOverview = false } = {}) {
  get.mockImplementation(async (path: string) => {
    if (path.startsWith("/api/v1/analytics/overview")) {
      if (failOverview) throw new Error("backend down");
      const periodDays = Number(new URL(`http://x${path}`).searchParams.get("period_days"));
      if (periodDays === 60) return overview([...days(30, { requests: 10, cost: 1 }, shiftDay(END, -30)), ...days(30, { requests: 20, cost: 2 })]);
      if (periodDays === 10) return overview(days(10, { requests: 5, cost: 5 }));
      return overview(days(periodDays, { requests: 20, cost: 2 }));
    }
    if (path === "/api/v1/organizations/current") return { budget_monthly_usd: budget };
    if (path === "/api/v1/teams") return [{ id: "t1", name: "Platform" }];
    throw new Error(`unmocked ${path}`);
  });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DashboardPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  auth.role = "admin";
});
afterEach(cleanup);

describe("DashboardPage", () => {
  it("shows each KPI with its change against the previous period", async () => {
    mockApi();
    renderPage();
    const kpis = await screen.findByRole("region", { name: "Key metrics" });
    const requests = within(kpis).getByText("Requests").closest("article") as HTMLElement;
    expect(within(requests).getByText("600")).toBeTruthy();
    // 30 days at 20/day against 30 days at 10/day: up 100%, judged as neutral for volume
    await waitFor(() => expect(requests.textContent).toContain("100.0%"));
    expect(requests.textContent).toContain("vs previous 30 days");
    const cost = within(kpis).getByText("Cost").closest("article") as HTMLElement;
    await waitFor(() => expect(cost.querySelector(".kpi__delta--bad")).not.toBeNull()); // cost doubling is bad news
  });

  it("explains the budget position and warns when the projection exceeds it", async () => {
    mockApi({ budget: "100" });
    renderPage();
    const panel = (await screen.findByText("Budget burn-down this month")).closest("section") as HTMLElement;
    // 10 days at $5 = $50 spent; projected 50 / 10 * 30 = $150 against a $100 budget
    expect(await within(panel).findByText(/Spent \$50\.00 of \$100\.00 budget \(50%\), projected \$150\.00 by month end\. On track to exceed the budget\./)).toBeTruthy();
    expect(within(panel).getByRole("img", { name: /Budget burn-down/ })).toBeTruthy();
  });

  it("tells the admin when no budget is set instead of drawing a made-up one", async () => {
    mockApi({ budget: null });
    renderPage();
    expect(await screen.findByText(/No monthly budget is set/)).toBeTruthy();
  });

  it("does not compare a 90-day window with a previous period the backend cannot return", async () => {
    mockApi();
    renderPage();
    await screen.findByRole("region", { name: "Key metrics" });
    fireEvent.click(screen.getByRole("button", { name: "90 days" }));
    await waitFor(() => expect(screen.getAllByText("No previous period to compare").length).toBe(4));
    const paths = get.mock.calls.map((c) => String(c[0]));
    expect(paths.some((p) => p.includes("period_days=180"))).toBe(false);
  });

  it("hides the org budget while a team is selected, and says why", async () => {
    mockApi();
    renderPage();
    await screen.findByRole("region", { name: "Key metrics" });
    fireEvent.change(await screen.findByLabelText("Filter by team"), { target: { value: "t1" } });
    expect(await screen.findByText(/applies to the whole organization/)).toBeTruthy();
  });

  it("shows spend by team and user to admins only", async () => {
    mockApi();
    renderPage();
    expect(await screen.findByRole("table", { name: "Cost by team" })).toBeTruthy();
    expect(screen.getByRole("table", { name: "Cost by user" })).toBeTruthy();
    cleanup();

    auth.role = "member";
    get.mockClear();
    mockApi();
    renderPage();
    await screen.findByRole("region", { name: "Key metrics" });
    expect(screen.queryByRole("table", { name: "Cost by team" })).toBeNull();
    expect(screen.queryByRole("table", { name: "Cost by user" })).toBeNull();
    expect(get.mock.calls.some((c) => c[0] === "/api/v1/organizations/current")).toBe(false);
  });

  it("marks the selected period for assistive technology", async () => {
    mockApi();
    renderPage();
    await screen.findByRole("region", { name: "Key metrics" });
    expect(screen.getByRole("button", { name: "30 days" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "7 days" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("shows an error when the overview cannot be loaded", async () => {
    mockApi({ failOverview: true });
    renderPage();
    expect(await screen.findByText("Unable to load overview")).toBeTruthy();
    expect(screen.getByText("backend down")).toBeTruthy();
  });
});
