import { ApiError, mapStatusToUserMessage, parseBackendError } from "./httpError";

export type GenerateResponse = {
  code: string;
};

const RAW_API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").trim();

function resolveApiBaseUrl(rawBaseUrl: string): string {
  const normalized = rawBaseUrl.replace(/\/+$/, "");
  if (!normalized) return "";

  // If frontend is served over https, explicit localhost/http backend URL
  // causes mixed-content/CORS issues in production.
  // In that case fallback to same-origin API routes proxied by nginx.
  if (typeof window !== "undefined") {
    const pageProtocol = window.location.protocol;
    const pageHostname = window.location.hostname;
    try {
      const parsed = new URL(normalized, window.location.origin);
      const isLocalBackend =
        parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1";
      const isCrossOrigin = parsed.origin !== window.location.origin;
      if (pageProtocol === "https:" && (isLocalBackend || isCrossOrigin)) {
        console.warn(
          `[api] Ignoring VITE_API_BASE_URL="${normalized}" on secure origin "${window.location.origin}". Using same-origin API routes instead.`,
        );
        return "";
      }
    } catch {
      // Keep normalized value for non-URL values such as relative paths.
      if (
        pageProtocol === "https:" &&
        (pageHostname === "ts.syharik.ru" || pageHostname.endsWith(".syharik.ru")) &&
        normalized.startsWith("http://")
      ) {
        return "";
      }
    }
  }

  return normalized;
}

const API_BASE_URL = resolveApiBaseUrl(RAW_API_BASE_URL);

function apiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (!API_BASE_URL) return normalizedPath;
  return `${API_BASE_URL}${normalizedPath}`;
}

export async function generateTsCode(file: File, schemaText: string): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  form.append("schema", schemaText);

  const res = await fetch(apiUrl("/generate"), {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const { status, detail, code } = await parseBackendError(res);
    throw new ApiError({
      status,
      code,
      detail,
      userMessage: mapStatusToUserMessage(status, detail, code),
    });
  }

  const data = (await res.json()) as GenerateResponse;
  return data.code;
}

export type InferSchemaResponse = {
  schema: string;
};

export async function inferSchemaExample(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(apiUrl("/infer-schema"), {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const { status, detail, code } = await parseBackendError(res);
    throw new ApiError({
      status,
      code,
      detail,
      userMessage: mapStatusToUserMessage(status, detail, code),
    });
  }

  const data = (await res.json()) as InferSchemaResponse;
  // Backend returns compact JSON string; frontend can reformat if needed.
  return data.schema;
}

