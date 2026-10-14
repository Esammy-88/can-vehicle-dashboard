import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The dev server proxies API and WebSocket traffic to the FastAPI backend,
// so the frontend never hard-codes the backend origin and no CORS is needed.
// Set BACKEND_URL to point at a backend on another port.
export default defineConfig(({ mode }) => {
  const backend = loadEnv(mode, ".", "").BACKEND_URL || "http://127.0.0.1:8000";
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: {
        "/api": backend,
        "/ws": { target: backend.replace(/^http/, "ws"), ws: true },
      },
    },
  };
});
