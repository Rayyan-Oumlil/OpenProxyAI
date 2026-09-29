// @vitest-environment node
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = resolve(__dirname, '..');
const SELF = resolve(__filename);

const FORBIDDEN: RegExp[] = [
  /testimonial/i,
  /trusted by/i,
  /\bSLA\b/,
  /99\.9/,
  /status:\s*operational/i,
  /1,600\+/,
  /calendly/i,
  /book a demo/i,
  /start (a )?trial/i,
];

function files(dir: string): string[] {
  return readdirSync(dir).flatMap(name => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return files(p);
    return /\.(tsx?|css|json)$/.test(p) ? [p] : [];
  });
}

describe('content lint', () => {
  it('contains no fabricated-evidence strings', () => {
    const hits = files(SRC)
      .filter(f => f !== SELF)
      .flatMap(f => {
        const text = readFileSync(f, 'utf8');
        return FORBIDDEN.filter(re => re.test(text)).map(re => `${f}: ${re}`);
      });
    expect(hits).toEqual([]);
  });
});
