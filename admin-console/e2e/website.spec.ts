import { expect, test } from "@playwright/test";

/**
 * The marketing site (web-app), served by the second webServer in playwright.config.ts.
 * Guards two real bugs: the desktop nav showed on phones (an inline `display: flex` beat the `hidden` class)
 * and pushed every page to 720 px wide, and several sections used fixed grid columns that cannot fit a phone.
 */
const SITE = "http://localhost:5199";
const PAGES = ["/", "/product", "/security", "/providers", "/pricing"];
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

  // The desktop nav links are not shown on phones (the Explore block below has its own links, so scope to the header).
  await expect(page.locator("header").getByRole("link", { name: "providers" })).toBeHidden();

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

test("on a phone the home page links to the detail pages instead of stacking them", async ({ browser }) => {
  const page = await (await browser.newContext({ viewport: { width: 390, height: 800 } })).newPage();
  await page.goto(SITE + "/");
  const explore = page.getByRole("region", { name: "Explore" });
  await expect(explore.getByRole("link", { name: /Pricing/ })).toBeVisible();
});

test("on a desktop the full navigation shows and the phone-only block does not", async ({ browser }) => {
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 } })).newPage();
  await page.goto(SITE + "/");
  await expect(page.locator("header").getByRole("link", { name: "providers" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Open menu" })).toBeHidden();
  await expect(page.getByRole("region", { name: "Explore" })).toBeHidden();
});
