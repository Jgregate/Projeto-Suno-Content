/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5173,
    // O frontend chama /api na própria origem e o Vite encaminha para a API.
    // Evita CORS e a resolução de localhost para ::1 no Windows (o uvicorn escuta em 127.0.0.1).
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
  // React + Router + Radix + Query ficam ~540 kB no chunk principal; Recharts já vai em chunk separado
  build: { chunkSizeWarningLimit: 600 },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
