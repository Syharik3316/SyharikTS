import { ApiError, mapStatusToUserMessage, parseBackendError } from '../httpError';
import { authorizedFetch } from './httpClient';
import type { UserPublic } from './authApi';

export type GenerationHistoryItem = {
  id: string;
  created_at: string;
  main_file_name: string;
};

export type GenerationHistoryDetail = GenerationHistoryItem & {
  generated_ts_code: string;
};

export type GenerationCheckInputResponse = {
  input_base64: string | null;
};

async function safeReadJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  try {
    return JSON.parse(text) as T;
  } catch {
    const snippet = text.slice(0, 300);
    throw new ApiError({
      status: res.status,
      detail: snippet || undefined,
      userMessage:
        'Сервер вернул неожиданный ответ (ожидался JSON). Проверьте, что backend обновлён и маршруты `/profile` / `/me/generations` доступны.',
    });
  }
}

export async function updateProfileRequest(params: {
  login: string | null;
  current_password: string;
  new_password: string | null;
}): Promise<UserPublic> {
  const res = await authorizedFetch('/profile', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      login: params.login,
      current_password: params.current_password,
      new_password: params.new_password,
    }),
  });

  if (!res.ok) {
    const { status, detail, code } = await parseBackendError(res);
    let userMessage = mapStatusToUserMessage(status, detail, code);
    if (status === 401 && typeof detail === 'string' && detail.trim()) {
      userMessage = detail;
    }
    throw new ApiError({ status, detail, code, userMessage });
  }

  return safeReadJson<UserPublic>(res);
}

export async function listGenerationsRequest(): Promise<GenerationHistoryItem[]> {
  const res = await authorizedFetch('/me/generations', { method: 'GET' });
  if (!res.ok) {
    const { status, detail, code } = await parseBackendError(res);
    throw new ApiError({
      status,
      detail,
      code,
      userMessage: mapStatusToUserMessage(status, detail, code),
    });
  }
  return safeReadJson<GenerationHistoryItem[]>(res);
}

export async function getGenerationDetailRequest(generationId: string): Promise<GenerationHistoryDetail> {
  const res = await authorizedFetch(`/me/generations/${generationId}`, { method: 'GET' });
  if (!res.ok) {
    const { status, detail, code } = await parseBackendError(res);
    throw new ApiError({
      status,
      detail,
      code,
      userMessage: mapStatusToUserMessage(status, detail, code),
    });
  }
  return safeReadJson<GenerationHistoryDetail>(res);
}

export async function getGenerationCheckInputRequest(generationId: string): Promise<GenerationCheckInputResponse> {
  const res = await authorizedFetch(`/me/generations/${generationId}/check-input`, { method: 'GET' });
  if (!res.ok) {
    const { status, detail, code } = await parseBackendError(res);
    throw new ApiError({
      status,
      detail,
      code,
      userMessage: mapStatusToUserMessage(status, detail, code),
    });
  }
  return safeReadJson<GenerationCheckInputResponse>(res);
}

export async function deleteGenerationRequest(generationId: string): Promise<void> {
  const res = await authorizedFetch(`/me/generations/${generationId}`, { method: 'DELETE' });
  if (!res.ok) {
    const { status, detail, code } = await parseBackendError(res);
    throw new ApiError({
      status,
      detail,
      code,
      userMessage: mapStatusToUserMessage(status, detail, code),
    });
  }
}

