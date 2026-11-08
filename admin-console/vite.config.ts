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
    // Playwright specs live in e2e/ and run under `npm run test:e2e`; e2e-record/ is the video recording (`npm run record:walkthrough`).
    exclude: ["e2e/**", "e2e-record/**", "node_modules/**", "dist/**"],
  },
});
