import { ApiError, mapStatusToUserMessage, parseBackendError } from '../httpError';
import { authorizedFetch } from './httpClient';

export type TokenUsageRequestItem = {
  id: string;
  created_at: string;
  main_file_name: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
};

export type TotalGenerationsStats = {
  total_generations_all_time: number;
};

export type TokenUsageSummary = {
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  requests_count: number;
  requests: TokenUsageRequestItem[];
};

async function safeReadJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  const isHtml = /^\s*</.test(text);
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError({
      status: res.status,
      detail: text.slice(0, 300) || undefined,
      userMessage: isHtml
        ? 'Сервер вернул HTML вместо JSON. Проверьте прокси nginx для маршрутов /stats и /observability.'
        : 'Сервер вернул неожиданный ответ (ожидался JSON).',
    });
  }
}

export async function getMyTokenUsageSummary(): Promise<TokenUsageSummary> {
  const res = await authorizedFetch('/me/token-usage', { method: 'GET' });
  if (!res.ok) {
    const { status, detail, code } = await parseBackendError(res);
    throw new ApiError({ status, detail, code, userMessage: mapStatusToUserMessage(status, detail, code) });
  }
  return safeReadJson<TokenUsageSummary>(res);
}

export async function getTotalGenerationsStats(): Promise<TotalGenerationsStats> {
  const res = await authorizedFetch('/stats/generations', { method: 'GET' });
  if (!res.ok) {
    const { status, detail, code } = await parseBackendError(res);
    throw new ApiError({ status, detail, code, userMessage: mapStatusToUserMessage(status, detail, code) });
  }
  return safeReadJson<TotalGenerationsStats>(res);
}
