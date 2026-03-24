import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { apiClient } from "../api/client";
import { decodeJwtExp } from "../lib/jwt";
import type { LoginRequest, RegisterRequest, TokenResponse, UserMeResponse } from "../api/types";

const ACCESS_KEY = "openproxy_access_token";
const REFRESH_KEY = "openproxy_refresh_token";

/** Fire a proactive refresh this many seconds before access token expiry. */
const REFRESH_BEFORE_SECS = 300; // 5 minutes

type AuthState = {
  token: string | null;
  user: UserMeResponse | null;
  isAuthenticating: boolean;
  isRestoring: boolean;
  error: string | null;
};

type AcceptInvitePayload = { token: string; name: string; password: string };

type AuthContextValue = AuthState & {
  login: (payload: LoginRequest) => Promise<void>;
  signup: (payload: RegisterRequest) => Promise<void>;
  acceptInvite: (payload: AcceptInvitePayload) => Promise<void>;
  logout: () => void | Promise<void>;
  applySsoCode: (code: string) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserMeResponse | null>(null);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [isRestoring, setIsRestoring] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Holds the latest scheduleRefresh to break the circular doRefresh ↔ scheduleRefresh dep.
  const scheduleRefreshRef = useRef<((accessToken: string) => void) | null>(null);

  const clearScheduledRefresh = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const doRefresh = useCallback(async () => {
    const refreshToken = localStorage.getItem(REFRESH_KEY);
    if (!refreshToken) {
      clearScheduledRefresh();
      setToken(null);
      setUser(null);
      return;
    }
    try {
      const tokens = await apiClient.post<TokenResponse>(
        "/api/v1/auth/refresh",
        undefined,
        refreshToken,
      );
      localStorage.setItem(ACCESS_KEY, tokens.access_token);
      if (tokens.refresh_token) {
        localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
      }
      setToken(tokens.access_token);
      scheduleRefreshRef.current?.(tokens.access_token);
    } catch {
      // Refresh failed (401 or network) — clear all auth state.
      clearScheduledRefresh();
      setToken(null);
      setUser(null);
      localStorage.removeItem(ACCESS_KEY);
      localStorage.removeItem(REFRESH_KEY);
    }
  }, [clearScheduledRefresh]);

  const scheduleRefresh = useCallback(
    (accessToken: string) => {
      clearScheduledRefresh();
      const exp = decodeJwtExp(accessToken);
      if (exp === null) return;
      const delayMs = (exp - Math.floor(Date.now() / 1000) - REFRESH_BEFORE_SECS) * 1000;
      if (delayMs <= 0) {
        void doRefresh();
        return;
      }
      intervalRef.current = setInterval(() => {
        clearInterval(intervalRef.current!);
        intervalRef.current = null;
        void doRefresh();
      }, delayMs);
    },
    [clearScheduledRefresh, doRefresh],
  );

  // Keep ref current so doRefresh can trigger rescheduling without a circular dep.
  scheduleRefreshRef.current = scheduleRefresh;

  // Clean up the refresh interval on unmount.
  useEffect(() => {
    return () => clearScheduledRefresh();
  }, [clearScheduledRefresh]);

  // Restore session from localStorage on mount.
  useEffect(() => {
    async function restore() {
      const stored = localStorage.getItem(ACCESS_KEY);
      if (!stored) {
        setIsRestoring(false);
        return;
      }
      try {
        const me = await apiClient.get<UserMeResponse>("/api/v1/auth/me", stored);
        setToken(stored);
        setUser(me);
        scheduleRefreshRef.current?.(stored);
      } catch {
        // Access token expired — try silent refresh with the refresh token.
        const refreshToken = localStorage.getItem(REFRESH_KEY);
        if (refreshToken) {
          try {
            const tokens = await apiClient.post<TokenResponse>(
              "/api/v1/auth/refresh",
              undefined,
              refreshToken,
            );
            localStorage.setItem(ACCESS_KEY, tokens.access_token);
            if (tokens.refresh_token) {
              localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
            }
            const me = await apiClient.get<UserMeResponse>(
              "/api/v1/auth/me",
              tokens.access_token,
            );
            setToken(tokens.access_token);
            setUser(me);
            scheduleRefreshRef.current?.(tokens.access_token);
          } catch {
            localStorage.removeItem(ACCESS_KEY);
            localStorage.removeItem(REFRESH_KEY);
          }
        } else {
          localStorage.removeItem(ACCESS_KEY);
        }
      } finally {
        setIsRestoring(false);
      }
    }
    void restore();
  }, []);

  const login = useCallback(async (payload: LoginRequest) => {
    setIsAuthenticating(true);
    setError(null);
    try {
      const tokens = await apiClient.post<TokenResponse>("/api/v1/auth/login", payload);
      localStorage.setItem(ACCESS_KEY, tokens.access_token);
      if (tokens.refresh_token) {
        localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
      }
      const me = await apiClient.get<UserMeResponse>("/api/v1/auth/me", tokens.access_token);
      setToken(tokens.access_token);
      setUser(me);
      scheduleRefreshRef.current?.(tokens.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in.");
      setToken(null);
      setUser(null);
      throw err;
    } finally {
      setIsAuthenticating(false);
    }
  }, []);

  const signup = useCallback(async (payload: RegisterRequest) => {
    setIsAuthenticating(true);
    setError(null);
    try {
      const tokens = await apiClient.post<TokenResponse>("/api/v1/auth/register", payload);
      localStorage.setItem(ACCESS_KEY, tokens.access_token);
      if (tokens.refresh_token) {
        localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
      }
      const me = await apiClient.get<UserMeResponse>("/api/v1/auth/me", tokens.access_token);
      setToken(tokens.access_token);
      setUser(me);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create account.");
      setToken(null);
      setUser(null);
      throw err;
    } finally {
      setIsAuthenticating(false);
    }
  }, []);

  const acceptInvite = useCallback(async (payload: AcceptInvitePayload) => {
    setIsAuthenticating(true);
    setError(null);
    try {
      const tokens = await apiClient.post<TokenResponse>("/api/v1/auth/accept-invite", payload);
      localStorage.setItem(ACCESS_KEY, tokens.access_token);
      if (tokens.refresh_token) {
        localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
      }
      const me = await apiClient.get<UserMeResponse>("/api/v1/auth/me", tokens.access_token);
      setToken(tokens.access_token);
      setUser(me);
      scheduleRefreshRef.current?.(tokens.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to accept invite.");
      throw err;
    } finally {
      setIsAuthenticating(false);
    }
  }, []);

  const applySsoCode = useCallback(async (code: string) => {
    setIsAuthenticating(true);
    setError(null);
    try {
      const tokens = await apiClient.exchangeSsoCode(code);
      localStorage.setItem(ACCESS_KEY, tokens.access_token);
      if (tokens.refresh_token) {
        localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
      }
      const me = await apiClient.get<UserMeResponse>("/api/v1/auth/me", tokens.access_token);
      setToken(tokens.access_token);
      setUser(me);
      scheduleRefreshRef.current?.(tokens.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "SSO sign-in failed.");
      setToken(null);
      setUser(null);
      throw err;
    } finally {
      setIsAuthenticating(false);
    }
  }, []);

  const logout = useCallback(async () => {
    clearScheduledRefresh();
    const t = token;
    setToken(null);
    setUser(null);
    setError(null);
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    if (t) {
      try {
        await apiClient.post("/api/v1/auth/logout", {}, t);
      } catch {
        // best-effort
      }
    }
  }, [token, clearScheduledRefresh]);

  const value = useMemo(
    () => ({ token, user, isAuthenticating, isRestoring, error, login, signup, acceptInvite, logout, applySsoCode }),
    [error, isAuthenticating, isRestoring, login, signup, acceptInvite, logout, applySsoCode, token, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
