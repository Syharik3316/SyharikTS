import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// .env lives next to backend in converter-agent/; Vite default is only frontend/.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "..", "");
  const proxyTarget =
    env.DEV_API_PROXY_TARGET?.trim() ||
    env.VITE_DEV_API_PROXY_TARGET?.trim() ||
    "http://127.0.0.1:8000";

  const apiProxy = {
    target: proxyTarget,
    changeOrigin: true,
  } as const;

  return {
    envDir: "..",
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      // Docker + nginx proxy passes Host header (ts.syharik.ru).
      // Vite by default blocks unknown hosts; allow our public domain.
      allowedHosts: ["ts.syharik.ru", "localhost", "127.0.0.1"],
      // Vite HMR websocket endpoint should match the public URL behind nginx.
      hmr: {
        protocol: "wss",
        host: "ts.syharik.ru",
        port: 443,
      },
      // Без этого при пустом VITE_API_BASE_URL запросы к /me/… попадают в SPA (HTML вместо JSON).
      proxy: {
        "/auth": apiProxy,
        "/me": apiProxy,
        "/generate": apiProxy,
        "/infer-schema": apiProxy,
        "/health": apiProxy,
        "/profile": {
          target: proxyTarget,
          changeOrigin: true,
          bypass(req) {
            if (req.method === "PATCH" || req.method === "OPTIONS") {
              return null;
            }
            return "/index.html";
          },
        },
      },
    },
  };
});
