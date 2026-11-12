import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../components/ui/ConfirmDialog";
import { ScimTokenCard } from "./ScimTokenCard";

vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ token: "tok", user: { role: "admin" } }) }));
vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), del: vi.fn() } }));

import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);
const post = vi.mocked(apiClient.post);
const del = vi.mocked(apiClient.del);

const BASE = "https://gw.example.com/scim/v2";
const none = { configured: false, token_prefix: null, created_at: null, last_used_at: null, scim_base_url: BASE };
const live = { configured: true, token_prefix: "scim_AbCdEf12", created_at: "2026-11-12T10:00:00Z", last_used_at: null, scim_base_url: BASE };

function renderCard() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ConfirmProvider>
        <ScimTokenCard />
      </ConfirmProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  del.mockReset();
  Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
});
afterEach(cleanup);

describe("ScimTokenCard", () => {
  it("offers to create a token when there is none, and shows the base URL", async () => {
    get.mockResolvedValue(none);
    renderCard();
    expect(await screen.findByText("No token")).toBeTruthy();
    expect(screen.getByText(BASE)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Create token" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Revoke token" })).toBeNull();
  });

  it("shows a new token once, in a dialog, and can copy it", async () => {
    get.mockResolvedValue(none);
    post.mockResolvedValue({ ...live, token: "scim_secretvalue", rotated: false });
    renderCard();
    await screen.findByText("No token");
    fireEvent.click(screen.getByRole("button", { name: "Create token" }));

    const dialog = await screen.findByRole("dialog", { name: "SCIM token created" });
    expect(within(dialog).getByText("scim_secretvalue")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "Copy token" }));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith("scim_secretvalue"));

    fireEvent.click(within(dialog).getByRole("button", { name: "Done" }));
    await waitFor(() => expect(screen.queryByText("scim_secretvalue")).toBeNull());
  });

  it("lists only the prefix of an existing token, never the token", async () => {
    get.mockResolvedValue(live);
    renderCard();
    expect(await screen.findByText("Token active")).toBeTruthy();
    expect(screen.getByText(/scim_AbCdEf12/)).toBeTruthy();
    expect(screen.getByText("Never")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Rotate token" })).toBeTruthy();
  });

  it("asks before rotating, and does nothing when cancelled", async () => {
    get.mockResolvedValue(live);
    renderCard();
    await screen.findByText("Token active");
    fireEvent.click(screen.getByRole("button", { name: "Rotate token" }));
    const confirmDialog = await screen.findByRole("dialog", { name: "Rotate the SCIM token?" });
    fireEvent.click(within(confirmDialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(post).not.toHaveBeenCalled();
  });

  it("rotates after confirmation and reveals the new token", async () => {
    get.mockResolvedValue(live);
    post.mockResolvedValue({ ...live, token: "scim_rotatedvalue", rotated: true });
    renderCard();
    await screen.findByText("Token active");
    fireEvent.click(screen.getByRole("button", { name: "Rotate token" }));
    const confirmDialog = await screen.findByRole("dialog", { name: "Rotate the SCIM token?" });
    fireEvent.click(within(confirmDialog).getByRole("button", { name: "Rotate token" }));
    expect(await screen.findByRole("dialog", { name: "SCIM token rotated" })).toBeTruthy();
    expect(screen.getByText("scim_rotatedvalue")).toBeTruthy();
  });

  it("revokes only after a destructive confirmation", async () => {
    get.mockResolvedValue(live);
    del.mockResolvedValue(undefined);
    renderCard();
    await screen.findByText("Token active");
    fireEvent.click(screen.getByRole("button", { name: "Revoke token" }));
    const confirmDialog = await screen.findByRole("dialog", { name: "Revoke the SCIM token?" });
    expect(del).not.toHaveBeenCalled();
    fireEvent.click(within(confirmDialog).getByRole("button", { name: "Revoke token" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("/api/v1/scim/token", "tok"));
  });

  it("says why when the plan does not allow SCIM", async () => {
    get.mockResolvedValue(none);
    post.mockRejectedValue(new Error("Upgrade your plan to enable 'sso_enabled'."));
    renderCard();
    await screen.findByText("No token");
    fireEvent.click(screen.getByRole("button", { name: "Create token" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Upgrade your plan");
  });

  it("shows an error instead of an empty card when the status cannot load", async () => {
    get.mockRejectedValue(new Error("Forbidden"));
    renderCard();
    expect((await screen.findByRole("alert")).textContent).toContain("Forbidden");
  });
});
