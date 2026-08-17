import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/",
  plugins: [react()],
  build: {
    outDir: "../src/nevis/ui/dist",
    emptyOutDir: true
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/api.generated.ts",
        "src/main.tsx",
        "src/vite-env.d.ts"
      ],
      reporter: ["text", "html"],
      thresholds: {
        statements: 60,
        branches: 50,
        functions: 60,
        lines: 60
      }
    }
  },
  server: {
    port: 5173,
    proxy: {
      "/ui": "http://127.0.0.1:8000",
      "/v1": "http://127.0.0.1:8000",
      "/search": "http://127.0.0.1:8000"
    }
  }
});
