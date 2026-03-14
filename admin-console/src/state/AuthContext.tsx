import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { apiClient } from "../api/client";
import type { LoginRequest, TokenResponse, UserMeResponse } from "../api/types";

const ACCESS_KEY = "openproxy_access_token";
const REFRESH_KEY = "openproxy_refresh_token";

type AuthState = {
  token: string | null;
  user: UserMeResponse | null;
  isAuthenticating: boolean;
  isRestoring: boolean;
  error: string | null;
};

type AuthContextValue = AuthState & {
  login: (payload: LoginRequest) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserMeResponse | null>(null);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [isRestoring, setIsRestoring] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Restore session from localStorage on mount
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
      } catch {
        // Token expired — try refresh
        const refreshToken = localStorage.getItem(REFRESH_KEY);
        if (refreshToken) {
          try {
            const tokens = await apiClient.post<TokenResponse>(
              "/api/v1/auth/refresh",
              { refresh_token: refreshToken }
            );
            localStorage.setItem(ACCESS_KEY, tokens.access_token);
            if (tokens.refresh_token) {
              localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
            }
            const me = await apiClient.get<UserMeResponse>("/api/v1/auth/me", tokens.access_token);
            setToken(tokens.access_token);
            setUser(me);
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
    restore();
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in.");
      setToken(null);
      setUser(null);
      throw err;
    } finally {
      setIsAuthenticating(false);
    }
  }, []);

  const logout = useCallback(async () => {
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
  }, [token]);

  const value = useMemo(
    () => ({ token, user, isAuthenticating, isRestoring, error, login, logout }),
    [error, isAuthenticating, isRestoring, login, logout, token, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
