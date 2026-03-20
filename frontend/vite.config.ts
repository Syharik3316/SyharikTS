import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
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
  },
});

