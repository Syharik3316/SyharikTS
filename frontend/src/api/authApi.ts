import { apiUrl, clearTokens, setTokens } from "./httpClient";

export type UserPublic = {
  id: string;
  email: string;
  login: string;
  is_email_verified: boolean;
  telegram_chat_id?: string | null;
  telegram_username?: string | null;
  telegram_first_name?: string | null;
  telegram_linked_at?: string | null;
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export async function loginRequest(login_or_email: string, password: string): Promise<TokenResponse> {
  const res = await fetch(apiUrl("/auth/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ login_or_email, password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : res.statusText;
    throw new Error(detail || "Login failed");
  }
  return data as TokenResponse;
}

export async function registerRequest(
  email: string,
  login: string,
  password: string,
  recaptcha_token: string | null,
): Promise<{ message: string }> {
  const res = await fetch(apiUrl("/auth/register"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, login, password, recaptcha_token }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : res.statusText;
    throw new Error(detail || "Registration failed");
  }
  return data as { message: string };
}

export class ResendCooldownError extends Error {
  retryAfterSeconds: number;

  constructor(message: string, retryAfterSeconds: number) {
    super(message);
    this.name = "ResendCooldownError";
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

export async function resendRegistrationCode(email: string): Promise<{ message: string }> {
  const res = await fetch(apiUrl("/auth/resend-registration-code"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 429) {
    const detail = data?.detail;
    const retry =
      typeof detail === "object" && detail !== null && typeof detail.retry_after_seconds === "number"
        ? detail.retry_after_seconds
        : 60;
    const msg =
      typeof detail === "object" && detail !== null && typeof detail.message === "string"
        ? detail.message
        : "Подождите перед повторной отправкой.";
    throw new ResendCooldownError(msg, retry);
  }
  if (!res.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : res.statusText;
    throw new Error(detail || "Request failed");
  }
  return data as { message: string };
}

export async function verifyEmailRequest(email: string, code: string): Promise<{ message: string }> {
  const res = await fetch(apiUrl("/auth/verify-email"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, code }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : res.statusText;
    throw new Error(detail || "Verification failed");
  }
  return data as { message: string };
}

export async function resetRequest(email: string, recaptcha_token: string | null): Promise<{ message: string }> {
  const res = await fetch(apiUrl("/auth/reset-request"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, recaptcha_token }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : res.statusText;
    throw new Error(detail || "Request failed");
  }
  return data as { message: string };
}

export async function resetConfirm(email: string, code: string, new_password: string): Promise<{ message: string }> {
  const res = await fetch(apiUrl("/auth/reset-confirm"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, code, new_password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : res.statusText;
    throw new Error(detail || "Reset failed");
  }
  return data as { message: string };
}

export async function fetchMe(accessToken: string): Promise<UserPublic> {
  const res = await fetch(apiUrl("/auth/me"), {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : res.statusText;
    throw new Error(detail || "Failed to load user");
  }
  return data as UserPublic;
}

export function persistSession(tokens: TokenResponse): void {
  setTokens(tokens.access_token, tokens.refresh_token);
}

export function logoutSession(): void {
  clearTokens();
}
