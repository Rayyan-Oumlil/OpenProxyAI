import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Page, RequestLogItem } from "../../api/types";
import { LogsPage } from "./LogsPage";

vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ token: "tok", user: { role: "admin" } }) }));
vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn() }, API_BASE_URL: "http://api.test" }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }));
vi.mock("./LogDetailDrawer", () => ({ LogDetailDrawer: ({ logId }: { logId: string | null }) => (logId ? <div role="dialog">drawer for {logId}</div> : null) }));

import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);

function row(overrides: Partial<RequestLogItem> = {}): RequestLogItem {
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
    ...overrides,
  };
}

function pageOf(items: RequestLogItem[], extra: Partial<Page<RequestLogItem>> = {}): Page<RequestLogItem> {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1, ...extra };
}

function mockApi(logs: (path: string) => Page<RequestLogItem>) {
  get.mockImplementation(async (path: string) => {
    if (path.startsWith("/api/v1/analytics/logs")) return logs(path);
    if (path.startsWith("/api/v1/analytics/policy")) return { total_policy_events: 7, by_action: [{ action: "block", count: 3 }] };
    if (path === "/api/v1/teams") return [{ id: "t1", name: "Platform" }];
    throw new Error(`unmocked ${path}`);
  });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <LogsPage />
    </QueryClientProvider>,
  );
}

const logCalls = () => get.mock.calls.map((c) => String(c[0])).filter((p) => p.startsWith("/api/v1/analytics/logs"));

beforeEach(() => {
  get.mockReset();
});
afterEach(cleanup);

describe("LogsPage", () => {
  it("lists requests with status, policy verdict, tokens, latency and cost", async () => {
    mockApi(() => pageOf([row(), row({ id: "l2", status: "error", policy_action: "block", policy_reason: "blocked_keyword", total_tokens: 0, latency_ms: 4, cost_usd: 0 })]));
    renderPage();
    await screen.findByText("blocked_keyword");
    const table = screen.getByRole("table", { name: "Request logs" }); // the filter menus also contain "Success" and "Error"
    expect(within(table).getByText("Success")).toBeTruthy();
    expect(within(table).getByText("Error")).toBeTruthy();
    expect(within(table).getByText("Blocked")).toBeTruthy();
    expect(screen.getByText("Policy events (30d): 7")).toBeTruthy();
  });

  it("opens the detail drawer for the clicked request", async () => {
    mockApi(() => pageOf([row()]));
    renderPage();
    fireEvent.click(await screen.findByText("openai/gpt-4o-mini"));
    expect(await screen.findByText("drawer for l1")).toBeTruthy();
  });

  it("sends the chosen filters to the API and returns to page 1", async () => {
    mockApi(() => pageOf([row()], { page: 2, total: 40, total_pages: 2 }));
    renderPage();
    await screen.findByText("openai/gpt-4o-mini");
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "error" } });
    fireEvent.change(screen.getByLabelText("Policy Reason"), { target: { value: "blocked_keyword" } });
    await waitFor(() => {
      const last = logCalls().at(-1)!;
      expect(last).toContain("status=error");
      expect(last).toContain("policy_reason=blocked_keyword");
      expect(last).toContain("page=1");
    });
  });

  it("keeps the filters on screen when they match nothing, so they can be cleared", async () => {
    mockApi((path) => (path.includes("status=error") ? pageOf([]) : pageOf([row()])));
    renderPage();
    await screen.findByText("openai/gpt-4o-mini");
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "error" } });

    expect(await screen.findByText("No requests match these filters")).toBeTruthy();
    const status = screen.getByLabelText("Status") as HTMLSelectElement; // still there
    fireEvent.change(status, { target: { value: "all" } });
    expect(await screen.findByText("openai/gpt-4o-mini")).toBeTruthy();
  });

  it("pages forward and back, with the buttons disabled at the ends", async () => {
    mockApi((path) => (path.includes("page=2") ? pageOf([row({ id: "l2", model: "second-page-model" })], { page: 2, total: 40, total_pages: 2 }) : pageOf([row()], { page: 1, total: 40, total_pages: 2 })));
    renderPage();
    await screen.findByText("openai/gpt-4o-mini");
    expect((screen.getByRole("button", { name: "Previous page" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("second-page-model")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Next page" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/Page 2 of 2/)).toBeTruthy();
  });

  it("shows the empty state when there are no logs at all", async () => {
    mockApi(() => pageOf([]));
    renderPage();
    expect(await screen.findByText("No request logs")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Request logs" })).toBeTruthy();
  });

  it("keeps the page and filters when loading fails, with a retry", async () => {
    get.mockRejectedValue(new Error("boom"));
    renderPage();
    expect(await screen.findByText("Unable to load logs")).toBeTruthy();
    expect(screen.getByLabelText("Status")).toBeTruthy();
    expect(screen.getByText("Try again")).toBeTruthy();
  });
});
