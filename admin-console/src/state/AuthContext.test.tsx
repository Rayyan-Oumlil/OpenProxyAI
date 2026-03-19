import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { ReactNode } from "react";
import { AuthProvider, useAuth } from "./AuthContext";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mockGet = vi.mocked(apiClient.get);
const mockPost = vi.mocked(apiClient.post);

/** Create a minimal JWT with a given exp (Unix seconds). */
function makeJwt(exp: number): string {
  const body = btoa(JSON.stringify({ exp, sub: "user1" }))
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
  return `header.${body}.sig`;
}

const NOW_SEC = 1_000_000;
const TTL_SEC = 3_600; // 1 hour

const mockUser = {
  id: "user1",
  org_id: "org1",
  email: "test@example.com",
  name: "Test",
  role: "admin",
  is_active: true,
};

function tokenResponse(accessToken: string, refreshToken = "rt") {
  return {
    access_token: accessToken,
    refresh_token: refreshToken,
    token_type: "bearer",
    expires_in: TTL_SEC,
  };
}

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

beforeEach(() => {
  vi.resetAllMocks(); // clears queued mockResolvedValueOnce between tests
  localStorage.clear();
  vi.spyOn(Date, "now").mockReturnValue(NOW_SEC * 1000);
});

afterEach(() => {
  vi.restoreAllMocks();
});

// Helper: render hook and wait for the session-restore phase to complete.
// NOTE: setInterval mocks must be set up AFTER this helper returns because
// waitFor() uses setInterval internally for polling.
async function renderAndRestore() {
  const { result } = renderHook(() => useAuth(), { wrapper });
  await waitFor(() => expect(result.current.isRestoring).toBe(false));
  return result;
}

describe("AuthContext — silent refresh scheduling", () => {
  it("calls setInterval with 5-min-before-expiry delay after login", async () => {
    const accessToken = makeJwt(NOW_SEC + TTL_SEC);
    mockPost.mockResolvedValueOnce(tokenResponse(accessToken, "rt1"));
    mockGet.mockResolvedValueOnce(mockUser);

    const result = await renderAndRestore();

    // Mock setInterval only AFTER waitFor so polling is not affected
    const setIntervalSpy = vi
      .spyOn(globalThis, "setInterval")
      .mockReturnValue(1 as unknown as ReturnType<typeof setInterval>);

    await act(async () => {
      await result.current.login({ email: "test@example.com", password: "pass" });
    });

    expect(setIntervalSpy).toHaveBeenCalledWith(
      expect.any(Function),
      (TTL_SEC - 300) * 1000,
    );
  });

  it("calls setInterval after session restore", async () => {
    const accessToken = makeJwt(NOW_SEC + TTL_SEC);
    localStorage.setItem("openproxy_access_token", accessToken);
    localStorage.setItem("openproxy_refresh_token", "rt_stored");

    // Spy without replacing the implementation so waitFor still works
    const setIntervalSpy = vi.spyOn(globalThis, "setInterval");
    mockGet.mockResolvedValueOnce(mockUser);

    const result = await renderAndRestore();

    expect(result.current.token).toBe(accessToken);
    expect(setIntervalSpy).toHaveBeenCalledWith(
      expect.any(Function),
      (TTL_SEC - 300) * 1000,
    );
  });

  it("calls POST /refresh with refresh token as Bearer when interval fires", async () => {
    const accessToken = makeJwt(NOW_SEC + TTL_SEC);
    const newAccessToken = makeJwt(NOW_SEC + TTL_SEC * 2);
    mockPost.mockResolvedValueOnce(tokenResponse(accessToken, "rt1"));
    mockGet.mockResolvedValueOnce(mockUser);

    const result = await renderAndRestore();

    let capturedCallback: (() => void) | null = null;
    vi.spyOn(globalThis, "setInterval").mockImplementation((cb) => {
      capturedCallback = cb as () => void;
      return 3 as unknown as ReturnType<typeof setInterval>;
    });

    await act(async () => {
      await result.current.login({ email: "test@example.com", password: "pass" });
    });

    expect(capturedCallback).not.toBeNull();

    mockPost.mockResolvedValueOnce(tokenResponse(newAccessToken, "rt2"));
    await act(async () => {
      capturedCallback!();
    });

    expect(mockPost).toHaveBeenCalledWith("/api/v1/auth/refresh", undefined, "rt1");
    expect(result.current.token).toBe(newAccessToken);
    expect(localStorage.getItem("openproxy_access_token")).toBe(newAccessToken);
    expect(localStorage.getItem("openproxy_refresh_token")).toBe("rt2");
  });

  it("clears auth state when refresh returns 401", async () => {
    const accessToken = makeJwt(NOW_SEC + TTL_SEC);
    mockPost.mockResolvedValueOnce(tokenResponse(accessToken, "rt"));
    mockGet.mockResolvedValueOnce(mockUser);

    const result = await renderAndRestore();

    let capturedCallback: (() => void) | null = null;
    vi.spyOn(globalThis, "setInterval").mockImplementation((cb) => {
      capturedCallback = cb as () => void;
      return 4 as unknown as ReturnType<typeof setInterval>;
    });

    await act(async () => {
      await result.current.login({ email: "test@example.com", password: "pass" });
    });

    expect(result.current.token).toBe(accessToken);

    mockPost.mockRejectedValueOnce(new Error("Unauthorized"));
    await act(async () => {
      capturedCallback!();
    });

    expect(result.current.token).toBeNull();
    expect(result.current.user).toBeNull();
    expect(localStorage.getItem("openproxy_access_token")).toBeNull();
    expect(localStorage.getItem("openproxy_refresh_token")).toBeNull();
  });

  it("calls clearInterval on logout", async () => {
    const accessToken = makeJwt(NOW_SEC + TTL_SEC);
    mockPost.mockResolvedValueOnce(tokenResponse(accessToken, "rt"));
    mockGet.mockResolvedValueOnce(mockUser);

    const result = await renderAndRestore();

    const intervalId = 99;
    vi.spyOn(globalThis, "setInterval").mockReturnValue(
      intervalId as unknown as ReturnType<typeof setInterval>,
    );
    const clearIntervalSpy = vi.spyOn(globalThis, "clearInterval");

    await act(async () => {
      await result.current.login({ email: "test@example.com", password: "pass" });
    });

    mockPost.mockResolvedValueOnce(undefined); // best-effort logout POST
    await act(async () => {
      await result.current.logout();
    });

    expect(clearIntervalSpy).toHaveBeenCalledWith(intervalId);
    expect(result.current.token).toBeNull();
  });
});
