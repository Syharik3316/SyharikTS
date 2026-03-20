export class ApiError extends Error {
  status: number;
  detail?: string;
  userMessage: string;

  constructor(params: { status: number; userMessage: string; detail?: string }) {
    super(params.userMessage);
    this.status = params.status;
    this.userMessage = params.userMessage;
    this.detail = params.detail;
  }
}

export function safeSlice(s: string, maxLen: number): string {
  if (s.length <= maxLen) return s;
  return s.slice(0, maxLen - 1) + "…";
}

export async function parseBackendError(res: Response): Promise<{ status: number; detail?: string }> {
  const status = res.status;

  // Try JSON first (FastAPI usually returns {detail: "..."}).
  try {
    const data = (await res.clone().json()) as any;
    const detail = typeof data?.detail === "string" ? (data.detail as string) : undefined;
    return { status, detail };
  } catch {
    // ignore
  }

  // Fallback to text.
  try {
    const text = await res.clone().text();
    const trimmed = text.trim();
    return { status, detail: trimmed || undefined };
  } catch {
    return { status };
  }
}

export function mapStatusToUserMessage(status: number, detail?: string): string {
  if (status === 401) return "Не удалось выполнить запрос.";
  if (status === 403) {
    return detail ? `Доступ запрещен: ${detail}` : "Доступ запрещен.";
  }
  if (status === 404) return "Запрошенный ресурс не найден.";
  if (status === 415) {
    const d = (detail || "").toLowerCase();
    if (d.includes("unsupported file type")) return "Файл данного типа не поддерживается.";
    return detail ? `Неподдерживаемый файл: ${detail}` : "Неподдерживаемый файл.";
  }
  if (status === 400 || status === 422) {
    const d = (detail || "").toLowerCase();
    if (d.includes("unsupported file type")) return "Файл данного типа не поддерживается.";
    if (d.includes("schema is required")) return "Нужно указать JSON-строку схемы.";
    if (detail) return `Ошибка входных данных: ${detail}`;
    return "Проверьте входные данные и повторите попытку.";
  }
  // Не раскрываем внутренние детали (особенно для ошибок ИИ/сервера).
  if (status >= 500) return "Ошибка сервера. Попробуйте позже.";

  return detail ? `Ошибка: ${detail}` : `Ошибка (HTTP ${status}).`;
}

