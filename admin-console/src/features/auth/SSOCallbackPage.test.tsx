import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SSOCallbackPage } from "./SSOCallbackPage";

const auth = vi.hoisted(() => ({
  applySsoCode: vi.fn(),
  error: null as string | null,
  isAuthenticating: false,
}));
vi.mock("../../state/AuthContext", () => ({ useAuth: () => auth }));

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/sso-callback" element={<SSOCallbackPage />} />
        <Route path="/" element={<h1>Home</h1>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  auth.applySsoCode.mockReset();
  auth.error = null;
  auth.isAuthenticating = false;
});
afterEach(cleanup);

describe("SSOCallbackPage", () => {
  it("exchanges the code once and goes home on success", async () => {
    auth.applySsoCode.mockResolvedValue(undefined);
    renderAt("/sso-callback?code=abc123");

    expect(await screen.findByRole("heading", { name: "Home" })).toBeTruthy();
    expect(auth.applySsoCode).toHaveBeenCalledTimes(1);
    expect(auth.applySsoCode).toHaveBeenCalledWith("abc123");
  });

  it("goes straight home, without calling the API, when there is no code", async () => {
    renderAt("/sso-callback");
    expect(await screen.findByRole("heading", { name: "Home" })).toBeTruthy();
    expect(auth.applySsoCode).not.toHaveBeenCalled();
  });

  it("stays on a failure page with the reason when the exchange fails", async () => {
    auth.applySsoCode.mockRejectedValue(new Error("bad code"));
    auth.error = "Invalid or expired code";
    renderAt("/sso-callback?code=expired");

    expect(await screen.findByRole("heading", { name: "Sign-in failed" })).toBeTruthy();
    expect(screen.getByText("Invalid or expired code")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Home" })).toBeNull();
  });

  it("shows progress while the exchange is running", async () => {
    auth.isAuthenticating = true;
    auth.applySsoCode.mockReturnValue(new Promise(() => undefined));
    renderAt("/sso-callback?code=slow");
    expect(await screen.findByRole("heading", { name: "Completing sign-in…" })).toBeTruthy();
    await waitFor(() => expect(auth.applySsoCode).toHaveBeenCalledTimes(1));
  });
});
