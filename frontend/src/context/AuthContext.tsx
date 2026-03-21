import React from "react";
import { useNavigate } from "react-router-dom";
import * as authApi from "../api/authApi";
import { apiUrl, clearTokens, getAccessToken, getRefreshToken } from "../api/httpClient";

type AuthContextValue = {
  user: authApi.UserPublic | null;
  ready: boolean;
  bootstrapping: boolean;
  login: (loginOrEmail: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
};

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const [user, setUser] = React.useState<authApi.UserPublic | null>(null);
  const [ready, setReady] = React.useState(false);
  const [bootstrapping, setBootstrapping] = React.useState(true);

  const refreshUser = React.useCallback(async () => {
    const access = getAccessToken();
    if (!access) {
      const rt = getRefreshToken();
      if (rt) {
        try {
          const res = await fetch(apiUrl("/auth/refresh"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: rt }),
          });
          if (res.ok) {
            const data = (await res.json()) as authApi.TokenResponse;
            authApi.persistSession(data);
            const me = await authApi.fetchMe(data.access_token);
            setUser(me);
            return;
          }
        } catch {
          /* fall through */
        }
      }
      clearTokens();
      setUser(null);
      return;
    }
    try {
      const me = await authApi.fetchMe(access);
      setUser(me);
    } catch {
      const rt = getRefreshToken();
      if (!rt) {
        clearTokens();
        setUser(null);
        return;
      }
      try {
        const res = await fetch(apiUrl("/auth/refresh"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: rt }),
        });
        if (!res.ok) throw new Error("refresh failed");
        const data = (await res.json()) as authApi.TokenResponse;
        authApi.persistSession(data);
        const me = await authApi.fetchMe(data.access_token);
        setUser(me);
      } catch {
        clearTokens();
        setUser(null);
      }
    }
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      await refreshUser();
      if (!cancelled) {
        setReady(true);
        setBootstrapping(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshUser]);

  const login = React.useCallback(
    async (loginOrEmail: string, password: string) => {
      const tokens = await authApi.loginRequest(loginOrEmail, password);
      authApi.persistSession(tokens);
      const me = await authApi.fetchMe(tokens.access_token);
      setUser(me);
      navigate("/upload", { replace: true });
    },
    [navigate],
  );

  const logout = React.useCallback(() => {
    authApi.logoutSession();
    setUser(null);
    navigate("/login", { replace: true });
  }, [navigate]);

  const value = React.useMemo<AuthContextValue>(
    () => ({
      user,
      ready,
      bootstrapping,
      login,
      logout,
      refreshUser,
    }),
    [user, ready, bootstrapping, login, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
