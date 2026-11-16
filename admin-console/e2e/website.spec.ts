import { expect, test } from "@playwright/test";

/**
 * The marketing site (web-app), served by the second webServer in playwright.config.ts.
 * Guards two real bugs: the desktop nav showed on phones (an inline `display: flex` beat the `hidden` class)
 * and pushed every page to 720 px wide, and several sections used fixed grid columns that cannot fit a phone.
 */
const SITE = "http://localhost:5199";
const PAGES = ["/", "/product", "/security", "/providers", "/compare", "/pricing"];
const WIDTHS = [320, 390, 768, 1280];

for (const width of WIDTHS) {
  test(`no page overflows horizontally at ${width}px`, async ({ browser }) => {
    const page = await (await browser.newContext({ viewport: { width, height: 800 } })).newPage();
    const wider: string[] = [];
    for (const path of PAGES) {
      await page.goto(SITE + path);
      await page.locator("h1, h2").first().waitFor();
      const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
      if (scrollWidth > width) wider.push(`${path} is ${scrollWidth}px wide`);
    }
    expect(wider).toEqual([]);
  });
}

test("on a phone the menu is a labelled toggle that closes on Escape and on navigation", async ({ browser }) => {
  const page = await (await browser.newContext({ viewport: { width: 390, height: 800 } })).newPage();
  await page.goto(SITE + "/");

  // The desktop nav links are not shown on phones (scope to the header, the page body has its own links).
  await expect(page.locator("header").getByRole("link", { name: "Integrations" })).toBeHidden();

  const open = page.getByRole("button", { name: "Open menu" });
  await expect(open).toHaveAttribute("aria-expanded", "false");
  await open.click();
  await expect(page.getByRole("button", { name: "Close menu" })).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator("#mobile-menu")).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.locator("#mobile-menu")).toBeHidden();

  await page.getByRole("button", { name: "Open menu" }).click();
  await page.locator("#mobile-menu").getByRole("link", { name: "pricing" }).click();
  await expect(page).toHaveURL(/\/pricing$/);
  await expect(page.locator("#mobile-menu")).toBeHidden();
});

test("on a phone the home page shows the demo command and the console tour, not a cut-down version", async ({ browser }) => {
  const page = await (await browser.newContext({ viewport: { width: 390, height: 800 } })).newPage();
  await page.goto(SITE + "/");
  await expect(page.locator("#try")).toBeVisible();
  await expect(page.locator("#tour").getByRole("tab", { name: "Request detail" })).toBeVisible();
  await expect(page.locator("#faq")).toBeVisible();
});

test("on a desktop the full navigation shows and the menu button does not", async ({ browser }) => {
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 } })).newPage();
  await page.goto(SITE + "/");
  await expect(page.locator("header").getByRole("link", { name: "Integrations" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Open menu" })).toBeHidden();
});
