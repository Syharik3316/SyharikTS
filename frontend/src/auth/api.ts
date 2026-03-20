import { ApiError, mapStatusToUserMessage, parseBackendError } from "../httpError";

export type UserPublic = {
  id: number;
  email: string;
  login: string;
  emailVerified: boolean;
};

export type AuthTokenResponse = {
  accessToken: string;
  user: UserPublic;
};

export type MessageResponse = {
  message: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, init);
  if (!res.ok) {
    const { status, detail } = await parseBackendError(res);
    throw new ApiError({
      status,
      detail,
      userMessage: mapStatusToUserMessage(status, detail),
    });
  }
  return (await res.json()) as T;
}

export async function authRegister(input: {
  email: string;
  login: string;
  password: string;
  recaptchaToken: string;
}): Promise<MessageResponse> {
  return requestJson<MessageResponse>("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: input.email,
      login: input.login,
      password: input.password,
      recaptchaToken: input.recaptchaToken,
    }),
  });
}

export async function authVerifyEmail(input: { email: string; code: string }): Promise<MessageResponse> {
  return requestJson<MessageResponse>("/auth/verify-email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: input.email, code: input.code }),
  });
}

export async function authLogin(input: {
  identifier: string;
  password: string;
  recaptchaToken: string;
}): Promise<AuthTokenResponse> {
  return requestJson<AuthTokenResponse>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      identifier: input.identifier,
      password: input.password,
      recaptchaToken: input.recaptchaToken,
    }),
  });
}

export async function authRequestPasswordReset(input: {
  identifier: string;
  recaptchaToken: string;
}): Promise<MessageResponse> {
  return requestJson<MessageResponse>("/auth/request-password-reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      identifier: input.identifier,
      recaptchaToken: input.recaptchaToken,
    }),
  });
}

export async function authResetPassword(input: {
  identifier: string;
  code: string;
  newPassword: string;
}): Promise<MessageResponse> {
  return requestJson<MessageResponse>("/auth/reset-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      identifier: input.identifier,
      code: input.code,
      newPassword: input.newPassword,
    }),
  });
}

export async function authMe(input: { accessToken: string }): Promise<{ user: UserPublic }> {
  return requestJson<{ user: UserPublic }>("/auth/me", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${input.accessToken}`,
    },
  });
}

