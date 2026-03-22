import { ApiError, mapStatusToUserMessage, parseBackendError } from '../httpError';
import { authorizedFetch } from './httpClient';

export type TelegramStatusResponse = {
  is_linked: boolean;
  telegram_chat_id: string | null;
  telegram_username: string | null;
  telegram_first_name: string | null;
  telegram_linked_at: string | null;
};

export type TelegramLinkCodeResponse = {
  link_command: string;
  code_expires_at: string;
  bot_url: string | null;
  bot_username: string | null;
};

async function readJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error('Сервер вернул неожиданный ответ.');
  }
}

export async function getTelegramStatusRequest(): Promise<TelegramStatusResponse> {
  const res = await authorizedFetch('/me/telegram/status', { method: 'GET' });
  if (!res.ok) {
    const { status, detail, code } = await parseBackendError(res);
    throw new ApiError({ status, detail, code, userMessage: mapStatusToUserMessage(status, detail, code) });
  }
  return readJson<TelegramStatusResponse>(res);
}

export async function createTelegramLinkCodeRequest(): Promise<TelegramLinkCodeResponse> {
  const res = await authorizedFetch('/me/telegram/link-code', { method: 'POST' });
  if (!res.ok) {
    const { status, detail, code } = await parseBackendError(res);
    throw new ApiError({ status, detail, code, userMessage: mapStatusToUserMessage(status, detail, code) });
  }
  return readJson<TelegramLinkCodeResponse>(res);
}

export async function unlinkTelegramRequest(): Promise<void> {
  const res = await authorizedFetch('/me/telegram/unlink', { method: 'POST' });
  if (!res.ok) {
    const { status, detail, code } = await parseBackendError(res);
    throw new ApiError({ status, detail, code, userMessage: mapStatusToUserMessage(status, detail, code) });
  }
}
