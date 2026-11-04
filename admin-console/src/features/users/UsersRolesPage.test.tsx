import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { UserResponse } from "../../api/types";
import { UsersRolesPage } from "./UsersRolesPage";

const auth = vi.hoisted(() => ({ role: "admin", id: "me" }));
vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ token: "tok", user: { id: auth.id, role: auth.role } }) }));
vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn(), patch: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);
const patch = vi.mocked(apiClient.patch);

function member(overrides: Partial<UserResponse>): UserResponse {
  return {
    id: "u1",
    org_id: "o1",
    email: "ada@example.com",
    name: "Ada",
    role: "developer",
    is_active: true,
    created_at: "2026-11-01T10:00:00Z",
    ...overrides,
  } as UserResponse;
}

const USERS = [member({ id: "me", email: "me@example.com", name: "Me", role: "admin" }), member({})];

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <UsersRolesPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  patch.mockReset();
  patch.mockResolvedValue(member({}));
  auth.role = "admin";
  auth.id = "me";
});
afterEach(cleanup);

describe("UsersRolesPage", () => {
  it("lists users with role, status and the person's own row marked", async () => {
    get.mockResolvedValue(USERS);
    renderPage();
    await screen.findByText("ada@example.com");
    expect(screen.getByText("(you)")).toBeTruthy();
    expect(screen.getAllByText("Active")).toHaveLength(2);
  });

  it("changes another user's role through the API", async () => {
    get.mockResolvedValue(USERS);
    renderPage();
    fireEvent.change(await screen.findByLabelText("Role for ada@example.com"), { target: { value: "viewer" } });
    await waitFor(() => expect(patch).toHaveBeenCalledWith("/api/v1/users/u1", { role: "viewer" }, "tok"));
  });

  it("deactivates another user, but never offers to change your own role or status", async () => {
    get.mockResolvedValue(USERS);
    renderPage();
    await screen.findByText("ada@example.com");
    fireEvent.click(screen.getByRole("button", { name: "Deactivate ada@example.com" }));
    await waitFor(() => expect(patch).toHaveBeenCalledWith("/api/v1/users/u1", { is_active: false }, "tok"));

    expect(screen.queryByLabelText("Role for me@example.com")).toBeNull();
    expect((screen.getByRole("button", { name: "Deactivate me@example.com" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("is read-only for a non-admin, and says so", async () => {
    auth.role = "viewer";
    auth.id = "u9";
    get.mockResolvedValue(USERS);
    renderPage();
    await screen.findByText("ada@example.com");
    expect(screen.getByText(/Read-only access/)).toBeTruthy();
    expect(screen.queryByLabelText("Role for ada@example.com")).toBeNull();
    expect((screen.getByRole("button", { name: "Deactivate ada@example.com" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("keeps the page header and shows an error with retry when loading fails", async () => {
    get.mockRejectedValue(new Error("boom"));
    renderPage();
    expect(await screen.findByText("Unable to load users")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Users & roles" })).toBeTruthy();
    expect(screen.getByText("Try again")).toBeTruthy();
  });

  it("shows the empty state inside the table area", async () => {
    get.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("No users in organization")).toBeTruthy();
    expect(within(screen.getByRole("heading", { name: "Users & roles" }).parentElement!).getByText(/Who can sign in/)).toBeTruthy();
  });
});
