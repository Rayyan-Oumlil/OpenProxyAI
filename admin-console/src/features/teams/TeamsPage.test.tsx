import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { TeamResponse } from "../../api/types";
import { ConfirmProvider } from "../../components/ui/ConfirmDialog";
import { TeamsPage } from "./TeamsPage";

const auth = vi.hoisted(() => ({ role: "admin" }));
vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ token: "tok", user: { id: "me", role: auth.role } }) }));
vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), del: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);
const del = vi.mocked(apiClient.del);

function team(overrides: Partial<TeamResponse> = {}): TeamResponse {
  return {
    id: "t1",
    name: "Platform",
    budget_monthly_usd: "250",
    member_count: 4,
    created_at: "2026-11-01T10:00:00Z",
    ...overrides,
  } as TeamResponse;
}

function mockApi(teams: TeamResponse[]) {
  get.mockImplementation(async (path: string) => {
    if (path === "/api/v1/teams") return teams;
    if (path === "/api/v1/users") return [];
    if (path.startsWith("/api/v1/teams/")) return { ...team(), members: [], invites: [] };
    throw new Error(`unmocked ${path}`);
  });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ConfirmProvider>
        <TeamsPage />
      </ConfirmProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  del.mockReset();
  del.mockResolvedValue(undefined);
  auth.role = "admin";
});
afterEach(cleanup);

describe("TeamsPage", () => {
  it("lists teams with budget and member count", async () => {
    mockApi([team(), team({ id: "t2", name: "Research", budget_monthly_usd: null, member_count: 0 })]);
    renderPage();
    await screen.findByText("Platform");
    expect(screen.getByText("$250.00")).toBeTruthy();
    expect(screen.getByText("Research")).toBeTruthy();
    expect(screen.getByText("—")).toBeTruthy(); // no budget set
  });

  it("opens the member manager for the chosen team", async () => {
    mockApi([team()]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Manage members of Platform" }));
    await waitFor(() => expect(get).toHaveBeenCalledWith("/api/v1/teams/t1", "tok"));
  });

  it("asks before deleting a team, and deletes only once confirmed", async () => {
    mockApi([team()]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Delete Platform" }));
    expect(await screen.findByRole("dialog", { name: "Delete team?" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(del).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Delete Platform" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete team" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("/api/v1/teams/t1", "tok"));
  });

  it("offers team creation to admins only", async () => {
    mockApi([team()]);
    renderPage();
    expect(await screen.findByRole("button", { name: /Create Team/ })).toBeTruthy();
    cleanup();

    auth.role = "viewer";
    mockApi([team()]);
    renderPage();
    expect(await screen.findByText(/Admin only/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Create Team/ })).toBeNull();
    expect(screen.queryByRole("table", { name: "Teams" })).toBeNull();
  });

  it("keeps the header and the create button when loading fails, with a retry", async () => {
    get.mockRejectedValue(new Error("boom"));
    renderPage();
    expect(await screen.findByText("Unable to load teams")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Teams" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Create Team/ })).toBeTruthy();
    expect(screen.getByText("Try again")).toBeTruthy();
  });

  it("shows the empty state", async () => {
    mockApi([]);
    renderPage();
    expect(await screen.findByText("No teams")).toBeTruthy();
  });
});
