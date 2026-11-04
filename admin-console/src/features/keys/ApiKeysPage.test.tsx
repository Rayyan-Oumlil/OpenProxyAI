import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ApiKeyResponse } from "../../api/types";
import { ConfirmProvider } from "../../components/ui/ConfirmDialog";
import { ApiKeysPage } from "./ApiKeysPage";

vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ token: "tok", user: { role: "admin" } }) }));
vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), del: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);
const post = vi.mocked(apiClient.post);
const del = vi.mocked(apiClient.del);

function key(overrides: Partial<ApiKeyResponse>): ApiKeyResponse {
  return {
    id: "k1",
    name: "ci-pipeline",
    key_prefix: "opai_dev_ab12",
    is_active: true,
    team_id: null,
    created_at: "2026-11-01T10:00:00Z",
    ...overrides,
  } as ApiKeyResponse;
}

function mockApi(keys: ApiKeyResponse[]) {
  get.mockImplementation(async (path: string) => {
    if (path === "/api/v1/api-keys") return keys;
    if (path === "/api/v1/teams") return [{ id: "t1", name: "Platform" }];
    throw new Error(`unmocked ${path}`);
  });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ConfirmProvider>
        <ApiKeysPage />
      </ConfirmProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  del.mockReset();
  del.mockResolvedValue(undefined);
});
afterEach(cleanup);

describe("ApiKeysPage", () => {
  it("lists keys with team, prefix and status", async () => {
    mockApi([key({ team_id: "t1" }), key({ id: "k2", name: "old", is_active: false })]);
    renderPage();
    await screen.findByText("ci-pipeline");
    const table = screen.getByRole("table", { name: "API keys" }); // "Platform" is also an option in the team dropdown
    expect(within(table).getByText("Platform")).toBeTruthy();
    expect(screen.getAllByText("opai_dev_ab12")).toHaveLength(2);
    expect(screen.getByText("Active")).toBeTruthy();
    expect(screen.getByText("Revoked")).toBeTruthy();
  });

  it("asks before revoking, and does nothing if declined", async () => {
    mockApi([key({})]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Revoke ci-pipeline" }));
    expect(await screen.findByRole("dialog", { name: "Revoke ci-pipeline?" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(del).not.toHaveBeenCalled();
  });

  it("revokes once the confirmation is accepted", async () => {
    mockApi([key({})]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Revoke ci-pipeline" }));
    fireEvent.click(await screen.findByRole("button", { name: "Revoke key" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("/api/v1/api-keys/k1", "tok"));
  });

  it("does not offer to revoke a key that is already revoked", async () => {
    mockApi([key({ is_active: false })]);
    renderPage();
    expect((await screen.findByRole("button", { name: "Revoke ci-pipeline" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("creates a key with the chosen team", async () => {
    mockApi([]);
    post.mockResolvedValue({ ...key({ id: "new" }), key: "opai_dev_secret" } as never);
    renderPage();
    fireEvent.change(await screen.findByLabelText("Key Name"), { target: { value: "my-app-key" } });
    fireEvent.change(await screen.findByLabelText("Team (optional)"), { target: { value: "t1" } });
    fireEvent.click(screen.getByRole("button", { name: "Create Key" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/api/v1/api-keys",
        { name: "my-app-key", permissions: ["proxy:llm"], expires_at: null, team_id: "t1" },
        "tok",
      ),
    );
  });

  it("keeps the page and its form when loading fails, with a retry", async () => {
    get.mockRejectedValue(new Error("boom"));
    renderPage();
    expect(await screen.findByText("Unable to load API keys")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "API keys" })).toBeTruthy();
    expect(screen.getByLabelText("Key Name")).toBeTruthy();
    expect(screen.getByText("Try again")).toBeTruthy();
  });

  it("shows the empty state under the form", async () => {
    mockApi([]);
    renderPage();
    expect(await screen.findByText("No API keys")).toBeTruthy();
  });
});
