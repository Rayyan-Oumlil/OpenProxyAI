import { defineConfig, devices } from "@playwright/test";

const PORT = 5174;
const SITE_PORT = 5199;

// The API is mocked per test (see e2e/), so the smoke test needs only the Vite dev server.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { baseURL: `http://localhost:${PORT}`, trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    // The website spec sets its own viewports, so one project is enough.
    { name: "mobile", use: { ...devices["Pixel 7"] }, testIgnore: /website\.spec\.ts/ },
  ],
  webServer: [
    {
      command: `npm run dev -- --port ${PORT} --strictPort`,
      url: `http://localhost:${PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      // The marketing site, for e2e/website.spec.ts.
      command: `npm run dev -- --port ${SITE_PORT} --strictPort`,
      cwd: "../web-app",
      url: `http://localhost:${SITE_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
