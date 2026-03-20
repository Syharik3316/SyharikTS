import React from "react";
import { authLogin, authMe, authRegister, authRequestPasswordReset, authResetPassword, authVerifyEmail } from "./api";
import { clearAccessToken, getAccessToken, setAccessToken } from "./tokenStore";
import type { AuthTokenResponse, MessageResponse, UserPublic } from "./api";

type AuthContextValue = {
  user: UserPublic | null;
  loading: boolean;
  login: (input: { identifier: string; password: string; recaptchaToken: string }) => Promise<AuthTokenResponse>;
  register: (input: {
    email: string;
    login: string;
    password: string;
    recaptchaToken: string;
  }) => Promise<MessageResponse>;
  verifyEmail: (input: { email: string; code: string }) => Promise<MessageResponse>;
  requestPasswordReset: (input: { identifier: string; recaptchaToken: string }) => Promise<MessageResponse>;
  resetPassword: (input: { identifier: string; code: string; newPassword: string }) => Promise<MessageResponse>;
  logout: () => void;
  refreshMe: () => Promise<void>;
};

const AuthContext = React.createContext<AuthContextValue | undefined>(undefined);

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

export function AuthProvider(props: { children: React.ReactNode }) {
  const { children } = props;
  const [user, setUser] = React.useState<UserPublic | null>(null);
  const [loading, setLoading] = React.useState(true);

  async function refreshMe() {
    const token = getAccessToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }

    try {
      const res = await authMe({ accessToken: token });
      setUser(res.user);
    } catch {
      clearAccessToken();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    refreshMe().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function login(input: { identifier: string; password: string; recaptchaToken: string }) {
    const res = await authLogin(input);
    setAccessToken(res.accessToken);
    setUser(res.user);
    return res;
  }

  async function register(input: {
    email: string;
    login: string;
    password: string;
    recaptchaToken: string;
  }) {
    return authRegister(input);
  }

  async function verifyEmail(input: { email: string; code: string }) {
    return authVerifyEmail(input);
  }

  async function requestPasswordReset(input: { identifier: string; recaptchaToken: string }) {
    return authRequestPasswordReset(input);
  }

  async function resetPassword(input: { identifier: string; code: string; newPassword: string }) {
    return authResetPassword(input);
  }

  function logout() {
    clearAccessToken();
    setUser(null);
  }

  const value: AuthContextValue = {
    user,
    loading,
    login,
    register,
    verifyEmail,
    requestPasswordReset,
    resetPassword,
    logout,
    refreshMe,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

