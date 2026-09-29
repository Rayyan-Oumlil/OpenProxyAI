// @vitest-environment node
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const vercel = JSON.parse(readFileSync(resolve(__dirname, '../../vercel.json'), 'utf8'));
const routes: string[] = JSON.parse(readFileSync(resolve(__dirname, '../../prerender-routes.json'), 'utf8'));

describe('vercel.json', () => {
  it('serves the static React Router client build', () => {
    expect(vercel.outputDirectory).toBe('build/client');
    expect(vercel.buildCommand).toBe('npm run build');
  });

  it('permanently redirects legacy URLs', () => {
    const map = Object.fromEntries(vercel.redirects.map((r: { source: string; destination: string; permanent: boolean }) => {
      expect(r.permanent).toBe(true);
      return [r.source, r.destination];
    }));
    expect(map).toEqual({ '/product': '/models', '/security': '/trust', '/providers': '/models' });
  });

  it('falls back to the SPA shell only for unknown paths', () => {
    expect(vercel.rewrites).toEqual([{ source: '/(.*)', destination: '/__spa-fallback.html' }]);
  });

  it('prerenders every page', () => {
    expect(routes).toEqual(['/', '/models', '/agents', '/trust', '/finops', '/engineering', '/pricing']);
  });
});
