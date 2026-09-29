import { readFileSync } from 'node:fs';
import type { Config } from '@react-router/dev/config';

const prerender: string[] = JSON.parse(readFileSync(new URL('./prerender-routes.json', import.meta.url), 'utf8'));

export default {
  appDirectory: 'src',
  ssr: false,
  prerender,
} satisfies Config;
