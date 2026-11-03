import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
  },
  test: {
    environment: "jsdom",
    globals: true,
    // Playwright specs live in e2e/ and run under `npm run test:e2e`.
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
  },
});
