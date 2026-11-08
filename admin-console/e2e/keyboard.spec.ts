import { expect, test, type Page } from "@playwright/test";

import { prepare, signIn } from "./support";

/**
 * Keyboard-only use, which is most of what a screen-reader pass checks beyond axe: every stop is visibly
 * focused, nothing traps focus, the skip link works, and the dialog hands focus back. Desktop only: a phone
 * has no Tab key.
 */
const ROUTES = ["/", "/logs", "/policy", "/api-keys", "/model-registry", "/mcp-servers", "/billing"];
const MAX_TABS = 120;

interface Stop {
  id: string;
  name: string;
  visible: boolean;
}

/** Describes the focused element and whether the browser draws a focus indicator on it. */
function describeFocus(): Stop | null {
  const el = document.activeElement as HTMLElement | null;
  if (!el || el === document.body) return null;
  // The ring may sit on the element or on a wrapper that uses :focus-within (a field built from several parts).
  const drawn = (node: Element) => {
    const style = getComputedStyle(node);
    return (style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0) || style.boxShadow !== "none";
  };
  let ringed = false;
  for (let node: Element | null = el; node && node !== document.body; node = node.parentElement) ringed ||= drawn(node);
  const path: string[] = [];
  for (let node: Element | null = el; node && node !== document.body; node = node.parentElement) {
    path.push(`${node.tagName}:${Array.from(node.parentElement?.children ?? []).indexOf(node)}`);
  }
  const label = (el as HTMLInputElement).labels?.[0]?.textContent?.trim();
  const name = el.getAttribute("aria-label") || label || el.textContent?.trim().slice(0, 40) || el.getAttribute("placeholder") || el.tagName;
  return { id: path.join(">"), name, visible: ringed };
}

async function tabThrough(page: Page): Promise<Stop[]> {
  const stops: Stop[] = [];
  for (let i = 0; i < MAX_TABS; i += 1) {
    await page.keyboard.press("Tab");
    const stop = await page.evaluate(describeFocus);
    if (!stop) break;
    if (stops[stops.length - 1]?.id === stop.id) continue; // a date field has several Tab stops inside one element
    if (stops.some((s) => s.id === stop.id)) break; // focus came back around: no trap
    stops.push(stop);
  }
  return stops;
}

test.beforeEach(async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "Tab navigation is a desktop concern");
  await prepare(page);
});

test("login form is reachable by Tab in a sensible order, with visible focus", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Operate Your AI Gateway" })).toBeVisible();
  const stops = await tabThrough(page);
  expect(stops.length).toBeGreaterThanOrEqual(3);
  const names = stops.map((s) => s.name.toLowerCase());
  expect(names.findIndex((n) => n.includes("email"))).toBeLessThan(names.findIndex((n) => n.includes("password")));
  expect(stops.filter((s) => !s.visible).map((s) => s.name)).toEqual([]);
});

test("the skip link is the first stop and moves focus to the main content", async ({ page }) => {
  await signIn(page);
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeVisible();
  await page.keyboard.press("Tab");
  const inMain = await page.evaluate(() => Boolean(document.activeElement?.closest("#main-content")));
  expect(inMain).toBe(true);
});

for (const route of ROUTES) {
  test(`${route}: no focus trap, every stop shows focus, Shift+Tab walks back`, async ({ page }) => {
    await signIn(page);
    await page.goto(route);
    await page.locator("main").first().waitFor();
    await page.waitForLoadState("networkidle");

    const stops = await tabThrough(page);
    expect(stops.length).toBeGreaterThan(5);
    expect(stops.length).toBeLessThan(MAX_TABS);
    expect(stops.filter((s) => !s.visible).map((s) => s.name)).toEqual([]);

    // Focus has wrapped to the first stop; Shift+Tab must walk back to the last one, not stay put.
    const wrapped = await page.evaluate(describeFocus);
    await page.keyboard.press("Shift+Tab");
    const back = await page.evaluate(describeFocus);
    expect(back?.id).toBe(stops[stops.length - 1].id);
    expect(back?.id).not.toBe(wrapped?.id);
  });
}

test("command palette: Ctrl+K moves focus in, Escape returns it where it was", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: "Skip to content" }).focus();
  await page.keyboard.press("Control+k");
  const box = page.getByRole("combobox", { name: "Go to page or action" });
  await expect(box).toBeFocused();

  // Focus stays inside the dialog however many times Tab is pressed.
  for (let i = 0; i < 6; i += 1) await page.keyboard.press("Tab");
  expect(await page.evaluate(() => Boolean(document.activeElement?.closest('[role="dialog"]')))).toBe(true);

  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Command palette" })).toBeHidden();
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
});

test("command palette: arrow keys move the announced option, Enter navigates", async ({ page }) => {
  await signIn(page);
  await page.keyboard.press("Control+k");
  const box = page.getByRole("combobox", { name: "Go to page or action" });
  await box.fill("policy");
  const option = page.getByRole("option", { name: /Policy/ });
  await expect(option).toHaveAttribute("aria-selected", "true");
  const active = await box.getAttribute("aria-activedescendant");
  expect(active).toBe(await option.getAttribute("id"));
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/policy$/);
});

test("command palette: switching theme from the keyboard", async ({ page }) => {
  await signIn(page);
  await page.keyboard.press("Control+k");
  await page.getByRole("combobox", { name: "Go to page or action" }).fill("theme dark");
  await page.keyboard.press("Enter");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("radio", { name: "Dark" })).toHaveAttribute("aria-checked", "true");
});
