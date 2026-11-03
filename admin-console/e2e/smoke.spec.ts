import { expect, test } from "@playwright/test";

import { ORG, prepare, signIn } from "./support";

test.beforeEach(async ({ page }) => {
  await prepare(page);
});

test("sign in, open the MCP page, review a drifted tool", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Operate Your AI Gateway" })).toBeVisible();

  await page.getByLabel("Email").fill("ada@example.com");
  await page.getByLabel("Password").fill("correct horse");
  // Navigating before login finishes would abort it; wait for the session to be established.
  await Promise.all([
    page.waitForResponse((r) => new URL(r.url()).pathname === "/api/v1/auth/me"),
    page.getByRole("button", { name: "Sign in" }).click(),
  ]);

  await page.goto("/mcp-servers");
  await expect(page.getByRole("heading", { name: "MCP servers" })).toBeVisible();

  await page.getByRole("cell", { name: /github/ }).first().click();
  const drift = page.getByRole("group", { name: "Changes to deploy since approval" });
  await expect(drift).toBeVisible();
  await expect(drift.getByLabel("Approved description")).toHaveText("Deploy a service");
  await expect(drift.getByLabel("Live description")).toContainText("evil.example");

  await page.getByRole("button", { name: "Approve deploy" }).click();
  await expect(page.getByRole("group", { name: "Changes to deploy since approval" })).toBeHidden();
  await expect(page.getByText("Approved", { exact: true })).toBeVisible();
});

test("a signed-out visit to a protected route shows the login page", async ({ page }) => {
  await page.goto("/mcp-servers");
  await expect(page.getByRole("heading", { name: "Operate Your AI Gateway" })).toBeVisible();
});

test("a request trace deep link shows where the time went", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email").fill("ada@example.com");
  await page.getByLabel("Password").fill("correct horse");
  await Promise.all([
    page.waitForResponse((r) => new URL(r.url()).pathname === "/api/v1/auth/me"),
    page.getByRole("button", { name: "Sign in" }).click(),
  ]);

  await page.goto("/logs/l1");
  await expect(page.getByRole("heading", { name: "Request trace" })).toBeVisible();
  const waterfall = page.getByRole("region", { name: "Where the time went" });
  await expect(waterfall.getByText("Upstream call")).toBeVisible();
  await expect(waterfall.getByText("100ms")).toBeVisible();
  await expect(page.getByRole("region", { name: "What happened" }).getByText("Miss")).toBeVisible();
});

test("removing a server asks first, starts on Cancel, and Escape backs out", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email").fill("ada@example.com");
  await page.getByLabel("Password").fill("correct horse");
  await Promise.all([
    page.waitForResponse((r) => new URL(r.url()).pathname === "/api/v1/auth/me"),
    page.getByRole("button", { name: "Sign in" }).click(),
  ]);

  await page.goto("/mcp-servers");
  await page.getByRole("button", { name: "Remove github" }).click();
  const dialog = page.getByRole("dialog", { name: "Remove github?" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("button", { name: "Remove github" })).toBeFocused(); // focus returns to the trigger
});

test("the dashboard shows KPIs with deltas and the budget burn-down", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email").fill("ada@example.com");
  await page.getByLabel("Password").fill("correct horse");
  await Promise.all([
    page.waitForResponse((r) => new URL(r.url()).pathname === "/api/v1/auth/me"),
    page.getByRole("button", { name: "Sign in" }).click(),
  ]);

  await expect(page.getByRole("heading", { name: "Gateway dashboard" })).toBeVisible();
  const kpis = page.getByRole("region", { name: "Key metrics" });
  await expect(kpis.getByText("vs previous 30 days").first()).toBeVisible();
  await expect(page.getByRole("img", { name: /Budget burn-down/ })).toBeVisible();
  await expect(page.getByRole("table", { name: "Cost by team" })).toBeVisible();
});

test("organization settings fill from the API in a real browser", async ({ page }) => {
  await signIn(page);
  await page.goto("/organization-settings");
  await expect(page.getByLabel("Organization name")).toHaveValue(ORG.name);
  await expect(page.getByLabel("Monthly budget (USD)")).toHaveValue(ORG.budget_monthly_usd);
});

test("the onboarding dialog opens for an organization without API keys", async ({ page }) => {
  // prepare() marks onboarding dismissed; undo that for this test so the first-run path is exercised.
  await page.addInitScript(() => localStorage.removeItem("openproxy_onboarding_dismissed"));
  await signIn(page);
  await expect(page.getByRole("dialog")).toBeVisible();
});
