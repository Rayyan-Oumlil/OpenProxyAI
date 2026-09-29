import { existsSync, readFileSync } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const routes = JSON.parse(readFileSync(join(root, 'prerender-routes.json'), 'utf8'));
const out = join(root, 'build', 'client');
const failures = [];

for (const route of routes) {
  const file = route === '/' ? join(out, 'index.html') : join(out, route, 'index.html');
  if (!existsSync(file)) {
    failures.push(`${route}: missing ${file}`);
    continue;
  }
  const html = readFileSync(file, 'utf8');
  if (!/<h1[\s>]/.test(html)) failures.push(`${route}: no <h1> in prerendered HTML`);
}
if (!existsSync(join(out, '__spa-fallback.html'))) failures.push('missing __spa-fallback.html (404 fallback)');

if (failures.length > 0) {
  console.error('check-prerender failed:\n' + failures.join('\n'));
  process.exit(1);
}
console.log(`check-prerender: ${routes.length} routes OK`);
