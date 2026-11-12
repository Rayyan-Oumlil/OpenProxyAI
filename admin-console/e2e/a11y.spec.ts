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
  "/model-registry",
  "/provider-health",
  "/mcp-servers",
  "/experiments",
  "/datasets",
  "/evaluators",
  "/eval-runs",
  "/conversations",
  "/conversations/c1",
  "/policy-plugins",
  "/analytics-query",
  "/scores",
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

/**
 * axe checks text contrast but not icons. An icon-only button whose icon matches its background (a white pencil on a
 * white page) passes axe and is invisible. This measures every icon inside a control against what is behind it, as
 * WCAG 1.4.11 (non-text contrast, 3:1) asks.
 */
async function lowContrastIcons(page: Page): Promise<string[]> {
  await page.waitForLoadState("networkidle");
  return page.evaluate(() => {
    type Rgba = [number, number, number, number];
    const canvas = document.createElement("canvas").getContext("2d")!;
    // The browser resolves any CSS colour (rgb, color-mix, color(srgb ...)) to pixels, so parse by painting one.
    const parse = (css: string): Rgba | null => {
      if (!css || css === "none" || css === "transparent") return null;
      canvas.clearRect(0, 0, 1, 1);
      canvas.fillStyle = "#000";
      canvas.fillStyle = css;
      canvas.fillRect(0, 0, 1, 1);
      const [r, g, b, a] = canvas.getImageData(0, 0, 1, 1).data;
      return a === 0 ? null : [r, g, b, a / 255];
    };
    const over = (top: Rgba, below: Rgba): Rgba => {
      const a = top[3] + below[3] * (1 - top[3]);
      const mix = (i: number) => (top[i] * top[3] + below[i] * below[3] * (1 - top[3])) / (a || 1);
      return [mix(0), mix(1), mix(2), a];
    };
    const background = (el: Element): Rgba => {
      const layers: Rgba[] = [];
      for (let node: Element | null = el; node; node = node.parentElement) {
        const c = parse(getComputedStyle(node).backgroundColor);
        if (c) layers.push(c);
        if (c && c[3] === 1) break;
      }
      return layers.reduceRight((below, layer) => over(layer, below), [255, 255, 255, 1] as Rgba);
    };
    const luminance = ([r, g, b]: Rgba) => {
      const lin = (v: number) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
      return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
    };
    const ratio = (a: Rgba, b: Rgba) => {
      const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
      return (hi + 0.05) / (lo + 0.05);
    };
    const problems: string[] = [];
    document.querySelectorAll("button svg, a svg, [role=button] svg").forEach((svg) => {
      const style = getComputedStyle(svg);
      const ink = parse(style.stroke) ?? parse(style.fill);
      if (!ink || svg.getBoundingClientRect().width === 0) return;
      const bg = background(svg);
      const drawn = over(ink, bg);
      const value = ratio(drawn, bg);
      if (value < 3) {
        const control = svg.closest("button, a, [role=button]")!;
        const name = control.getAttribute("aria-label") || control.textContent?.trim() || "(unnamed)";
        problems.push(`${name}: icon contrast ${value.toFixed(2)}:1`);
      }
    });
    return problems;
  });
}

/** A page wider than its viewport (WCAG 1.4.10 reflow) also pushes controls under each other, so clicks miss. */
test.describe("reflow", () => {
  test.beforeEach(async ({ page }) => {
    await prepare(page);
  });

  for (const route of ROUTES) {
    test(`screen ${route} fits the viewport width`, async ({ page }) => {
      await signIn(page);
      await page.goto(route);
      await page.locator("main").first().waitFor();
      await page.waitForLoadState("networkidle");
      const { clientWidth, scrollWidth } = await page.evaluate(() => ({
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
      }));
      expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
    });
  }
});

/** A dialog pinned by its corner instead of centred runs off the screen and strands its buttons (it did, for every dialog). */
test.describe("dialogs", () => {
  test.beforeEach(async ({ page }) => {
    await prepare(page);
  });

  for (const [route, open] of [
    ["/evaluators", async (page: Page) => { await page.getByRole("button", { name: /New evaluator/ }).click(); await page.getByLabel("Type").selectOption("llm_judge"); }],
    ["/eval-runs", async (page: Page) => { await page.getByRole("button", { name: /Start a run/ }).click(); }],
    ["/conversations", async (page: Page) => { await page.getByRole("button", { name: /New conversation/ }).click(); }],
  ] as const) {
    test(`the tallest dialog on ${route} stays inside the window with its buttons reachable`, async ({ page }) => {
      await signIn(page);
      await page.goto(route);
      await page.locator("main").first().waitFor();
      await open(page);
      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible();
      const { box, viewport } = await page.evaluate(() => {
        const r = document.querySelector("[role=dialog]")!.getBoundingClientRect();
        return { box: { top: r.top, bottom: r.bottom, left: r.left, right: r.right }, viewport: { w: innerWidth, h: innerHeight } };
      });
      expect(box.top).toBeGreaterThanOrEqual(0);
      expect(box.bottom).toBeLessThanOrEqual(viewport.h + 1);
      expect(box.left).toBeGreaterThanOrEqual(0);
      expect(box.right).toBeLessThanOrEqual(viewport.w + 1);
      await dialog.getByRole("button", { name: /Create evaluator|Start run|Start conversation/ }).scrollIntoViewIfNeeded();
      await expect(dialog.getByRole("button", { name: /Create evaluator|Start run|Start conversation/ })).toBeInViewport();
    });
  }
});

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

    test("command palette open", async ({ page }) => {
      await signIn(page);
      await page.getByRole("button", { name: /^Search/ }).click();
      await expect(page.getByRole("dialog", { name: "Command palette" })).toBeVisible();
      expect(await audit(page)).toEqual([]);
    });

    test("policy: Data and routing tab with a preview result on screen", async ({ page }) => {
      await signIn(page);
      await page.goto("/policy");
      await page.getByRole("tab", { name: "Data and routing" }).click();
      await page.getByLabel("Model", { exact: true }).fill("openai/gpt-4o-mini");
      await page.getByLabel("Prompt").fill("my ssn is 123-45-6789");
      await page.getByRole("button", { name: "Preview", exact: true }).click();
      await expect(page.getByText("Refused by routing")).toBeVisible();
      expect(await audit(page)).toEqual([]);
      expect(await lowContrastIcons(page)).toEqual([]);
    });

    test("datasets: an open dataset with the import dialog", async ({ page }) => {
      await signIn(page);
      await page.goto("/datasets");
      await page.getByText("support-regressions").click();
      await expect(page.getByText("How do I reset my password?")).toBeVisible();
      expect(await audit(page)).toEqual([]);
      expect(await lowContrastIcons(page)).toEqual([]);
      await page.getByRole("button", { name: /Import from traffic/ }).click();
      await expect(page.getByRole("dialog", { name: /Import into/ })).toBeVisible();
      expect(await audit(page)).toEqual([]);
    });

    test("conversations: a thread, the context drawer and the new-conversation dialog", async ({ page }) => {
      await signIn(page);
      await page.goto("/conversations/c1");
      await expect(page.getByRole("article", { name: "Assistant, message 2" })).toBeVisible();
      expect(await audit(page)).toEqual([]);
      expect(await lowContrastIcons(page)).toEqual([]);
      await page.getByRole("button", { name: "Context sent" }).click();
      await expect(page.getByText("Earlier messages held back")).toBeVisible();
      expect(await audit(page)).toEqual([]);
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: /New conversation/ }).click();
      await expect(page.getByRole("dialog", { name: "New conversation" })).toBeVisible();
      expect(await audit(page)).toEqual([]);
    });

    test("analytics query: a result on screen", async ({ page }) => {
      await signIn(page);
      await page.goto("/analytics-query");
      await expect(page.getByRole("option", { name: "Requests" })).toBeAttached();
      await page.getByRole("button", { name: /Run query/ }).click();
      await expect(page.getByText("openai/gpt-4o-mini")).toBeVisible();
      expect(await audit(page)).toEqual([]);
      expect(await lowContrastIcons(page)).toEqual([]);
    });

    test("policy plugins: a listed plugin and the upload form", async ({ page }) => {
      await signIn(page);
      await page.goto("/policy-plugins");
      await expect(page.getByText("no-codenames")).toBeVisible();
      expect(await audit(page)).toEqual([]);
      expect(await lowContrastIcons(page)).toEqual([]);
    });

    test("scores: the summary and the recent scores", async ({ page }) => {
      await signIn(page);
      await page.goto("/scores");
      await expect(page.getByText("loved it")).toBeVisible();
      expect(await audit(page)).toEqual([]);
      expect(await lowContrastIcons(page)).toEqual([]);
    });

    test("evaluators: the new-evaluator dialog for a judge", async ({ page }) => {
      await signIn(page);
      await page.goto("/evaluators");
      await page.getByRole("button", { name: /New evaluator/ }).click();
      await page.getByLabel("Type").selectOption("llm_judge");
      await expect(page.getByLabel("Judge model")).toBeVisible();
      expect(await audit(page)).toEqual([]);
    });

    test("eval runs: an open run and the start dialog", async ({ page }) => {
      await signIn(page);
      await page.goto("/eval-runs");
      await page.getByText("openai/gpt-4o-mini").first().click();
      await expect(page.getByText("Blocked by policy.")).toBeVisible();
      expect(await audit(page)).toEqual([]);
      expect(await lowContrastIcons(page)).toEqual([]);
      await page.getByRole("button", { name: /Start a run/ }).click();
      await expect(page.getByRole("dialog", { name: "Start an eval run" })).toBeVisible();
      expect(await audit(page)).toEqual([]);
    });

    test("policy: the Evaluation tab with capture and the gate on", async ({ page }) => {
      await signIn(page);
      await page.goto("/policy");
      await page.getByRole("tab", { name: "Evaluation" }).click();
      await page.getByLabel("Keep a sample of delivered requests").check();
      await page.getByLabel("Require a passing eval run before a prompt goes live").check();
      await expect(page.getByLabel("Pass rate required (%)")).toBeVisible();
      expect(await audit(page)).toEqual([]);
    });

    test("experiments: an adaptive test with its results open", async ({ page }) => {
      await signIn(page);
      await page.goto("/experiments");
      await expect(page.getByText("Adaptive", { exact: true })).toBeVisible();
      await page.getByRole("button", { name: /Show details for mini vs full results/ }).click();
      await expect(page.getByText("Chance best")).toBeVisible();
      expect(await audit(page)).toEqual([]);
      expect(await lowContrastIcons(page)).toEqual([]);
    });

    test("playground: the promotion dialog for a draft prompt", async ({ page }) => {
      await signIn(page);
      await page.goto("/playground");
      await page.getByRole("button", { name: "Templates", exact: true }).click();
      await page.getByRole("button", { name: "Promote support-agent v2" }).click();
      await expect(page.getByText(/Not ready/)).toBeVisible();
      await page.getByLabel(/Promote anyway/).check();
      expect(await audit(page)).toEqual([]);
    });

    for (const route of ROUTES) {
      test(`screen ${route}`, async ({ page }) => {
        await signIn(page);
        await page.goto(route);
        await page.locator("main").first().waitFor();
        expect(await audit(page)).toEqual([]);
        expect(await lowContrastIcons(page)).toEqual([]);
      });
    }
  });
}
