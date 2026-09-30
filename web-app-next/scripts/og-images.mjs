import { mkdirSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const routes = JSON.parse(readFileSync(join(root, 'prerender-routes.json'), 'utf8'));
const base = process.env.OG_BASE_URL ?? 'http://localhost:4173';
const outDir = join(root, 'public', 'og');
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, reducedMotion: 'reduce' });
for (const route of routes) {
  const res = await page.goto(`${base}${route}`, { waitUntil: 'networkidle' });
  if (!res?.ok()) throw new Error(`og-images: ${route} returned ${res?.status()}`);
  const slug = route === '/' ? 'home' : route.slice(1);
  await page.screenshot({ path: join(outDir, `${slug}.png`) });
  console.log(`og-images: wrote og/${slug}.png`);
}
await browser.close();
