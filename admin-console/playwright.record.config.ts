import { defineConfig } from "@playwright/test";

/**
 * Records the demo walkthrough as a video against a RUNNING demo stack (no mocks, no web server started here):
 *
 *   docker compose -f docker-compose.demo.yml up -d --build --wait api console
 *   npm run record:walkthrough
 *
 * The video lands in walkthrough-video/ (git-ignored). Run it against a fresh stack: the budget step needs the
 * demo user's daily budget unspent (`docker compose -f docker-compose.demo.yml down -v` resets it).
 */
export default defineConfig({
  testDir: "./e2e-record",
  timeout: 300_000,
  retries: 0,
  workers: 1,
  reporter: "list",
  outputDir: "./walkthrough-video/raw",
  use: {
    baseURL: process.env.CONSOLE_URL ?? "http://localhost:5173",
    viewport: { width: 1280, height: 720 },
    video: { mode: "on", size: { width: 1280, height: 720 } },
    launchOptions: { slowMo: 120 },
  },
});
