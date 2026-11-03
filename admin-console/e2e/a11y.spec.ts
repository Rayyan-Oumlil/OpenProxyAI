import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { prepare, signIn } from "./support";

/**
 * WCAG 2.1 A and AA, checked by axe on every console screen, in both themes. The API is mocked, so
 * screens without a mock render their error state: structure and contrast are still audited there.
 */
const ROUTES = [
  "/",
  "/logs",
  "/logs/l1",
  "/audit",
  "/playground",
  "/policy",
  "/api-keys",
  "/provider-keys",
  "/provider-health",
  "/mcp-servers",
  "/experiments",
  "/teams",
  "/users-roles",
  "/organization-settings",
  "/billing",
];

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function audit(page: Page) {
  // Let lazy chunks, queries and transitions settle before scanning.
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(300);
  const { violations } = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  return violations.map((v) => `${v.id} (${v.impact}) x${v.nodes.length}: ${v.nodes[0].target.join(" ")}`);
}

for (const theme of ["light", "dark"] as const) {
  test.describe(`${theme} theme`, () => {
    test.beforeEach(async ({ page }) => {
      await prepare(page);
      await page.addInitScript((mode) => localStorage.setItem("opai-theme", mode), theme);
    });

    test("login page", async ({ page }) => {
      await page.goto("/");
      await expect(page.getByRole("heading", { name: "Operate Your AI Gateway" })).toBeVisible();
      expect(await audit(page)).toEqual([]);
    });

    test("signup page", async ({ page }) => {
      await page.goto("/signup");
      await expect(page.getByRole("heading").first()).toBeVisible();
      expect(await audit(page)).toEqual([]);
    });

    for (const route of ROUTES) {
      test(`screen ${route}`, async ({ page }) => {
        await signIn(page);
        await page.goto(route);
        await page.locator("main").first().waitFor();
        expect(await audit(page)).toEqual([]);
      });
    }
  });
}
