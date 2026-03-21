const ACCESS_KEY = "syharikts_access_token";
const REFRESH_KEY = "syharikts_refresh_token";

const RAW_API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").trim();

function resolveApiBaseUrl(rawBaseUrl: string): string {
  const normalized = rawBaseUrl.replace(/\/+$/, "");
  if (!normalized) return "";

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

export const API_BASE_URL = resolveApiBaseUrl(RAW_API_BASE_URL);

export function apiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (!API_BASE_URL) return normalizedPath;
  return `${API_BASE_URL}${normalizedPath}`;
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const rt = getRefreshToken();
  if (!rt) return false;
  try {
    const res = await fetch(apiUrl("/auth/refresh"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) return false;
    const data = (await res.json()) as { access_token?: string; refresh_token?: string };
    if (!data.access_token || !data.refresh_token) return false;
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

function dedupedRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = refreshAccessToken().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

/**
 * Fetch with Bearer access token; on 401 tries refresh once and retries.
 */
export async function authorizedFetch(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith("http") ? path : apiUrl(path);
  const headers = new Headers(init?.headers);
  const access = getAccessToken();
  if (access) headers.set("Authorization", `Bearer ${access}`);

  let res = await fetch(url, { ...init, headers });
  if (res.status !== 401) return res;

  const ok = await dedupedRefresh();
  if (!ok) {
    clearTokens();
    return res;
  }

  const headers2 = new Headers(init?.headers);
  const access2 = getAccessToken();
  if (access2) headers2.set("Authorization", `Bearer ${access2}`);
  return fetch(url, { ...init, headers: headers2 });
}
