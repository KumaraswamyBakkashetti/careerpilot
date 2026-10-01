import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.BACKEND_PROXY_TARGET || "http://127.0.0.1:8000";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      watch: { usePolling: env.CP_VITE_POLLING === "true", interval: 250 },
      proxy: { "/health": { target }, "/api": { target } },
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      clearMocks: true,
    },
  };
});
