import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

const ROUTES: string[] = JSON.parse(readFileSync(new URL('../prerender-routes.json', import.meta.url), 'utf8'));

// Vercel Analytics only exists on Vercel; locally its script 404s (ledger ruling R2).
const isExpectedLocalNoise = (text: string) => text.includes('/_vercel/insights');

for (const route of ROUTES) {
  test.describe(route, () => {
    test('renders headline and body with JavaScript disabled', async ({ browser }) => {
      const ctx = await browser.newContext({ javaScriptEnabled: false });
      const page = await ctx.newPage();
      await page.goto(route);
      await expect(page.locator('h1')).toHaveCount(1);
      expect((await page.locator('main').innerText()).length).toBeGreaterThan(200);
      await ctx.close();
    });

    test('loads directly without console errors', async ({ page }) => {
      const errors: string[] = [];
      page.on('console', m => { if (m.type() === 'error' && !isExpectedLocalNoise(m.location().url + m.text())) errors.push(m.text()); });
      page.on('pageerror', e => errors.push(e.message));
      await page.goto(route);
      await page.waitForLoadState('networkidle');
      expect(errors).toEqual([]);
    });

    test('has no horizontal scroll', async ({ page }) => {
      await page.goto(route);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(0);
    });
  });
}

test('map scenes match visual snapshots', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop', 'snapshots are desktop-only');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  for (const route of ['/', '/models', '/agents', '/trust', '/finops']) {
    await page.goto(route);
    await expect(page.locator('figure svg[role="img"]').first()).toHaveScreenshot(`map-${route === '/' ? 'home' : route.slice(1)}.png`);
  }
});

test('command palette navigates', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop', 'keyboard shortcut is desktop-only');
  await page.goto('/');
  await page.keyboard.press('Control+k');
  await page.getByLabel('Search pages').fill('trust');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/trust$/);
});

test('PII demo redacts live', async ({ page }) => {
  await page.goto('/trust');
  await page.getByLabel(/your prompt/i).fill('mail me at a@b.io');
  await expect(page.locator('output')).toContainText('mail me at [REDACTED]');
});

test('audit chain breaks on edit', async ({ page }) => {
  await page.goto('/trust');
  await page.getByLabel('Action for entry 3').fill('export_all_logs');
  await expect(page.getByText('✗ broken')).toHaveCount(3);
});
