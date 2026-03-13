import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { apiClient } from "../api/client";
import type { LoginRequest, TokenResponse, UserMeResponse } from "../api/types";

type AuthState = {
  token: string | null;
  user: UserMeResponse | null;
  isAuthenticating: boolean;
  error: string | null;
};

type AuthContextValue = AuthState & {
  login: (payload: LoginRequest) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

type AuthProviderProps = {
  children: ReactNode;
};

export function AuthProvider({ children }: AuthProviderProps) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserMeResponse | null>(null);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = useCallback(async (payload: LoginRequest) => {
    setIsAuthenticating(true);
    setError(null);
    try {
      const tokens = await apiClient.post<TokenResponse>("/api/v1/auth/login", payload);
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

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setError(null);
  }, []);

  const value = useMemo(
    () => ({
      token,
      user,
      isAuthenticating,
      error,
      login,
      logout,
    }),
    [error, isAuthenticating, login, logout, token, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

