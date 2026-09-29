import { existsSync, readdirSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const REQUIRED = ['tests', 'alembic/versions', 'app/routes', 'app/services'];
const TEST_FN = /^\s*(?:async\s+)?def\s+test_/gm;

function pyModules(dir) {
  return readdirSync(dir).filter(f => f.endsWith('.py') && f !== '__init__.py');
}

export function collectRepoStats(repoRoot) {
  const backend = join(repoRoot, 'backend');
  for (const rel of REQUIRED) {
    const p = join(backend, rel);
    if (!existsSync(p)) {
      throw new Error(`repo-stats: missing ${p} — the site build must run with the full repository checked out`);
    }
  }
  const testsDir = join(backend, 'tests');
  const testFiles = readdirSync(testsDir).filter(f => /^test_.*\.py$/.test(f));
  const testFunctions = testFiles.reduce(
    (sum, f) => sum + (readFileSync(join(testsDir, f), 'utf8').match(TEST_FN)?.length ?? 0),
    0,
  );
  return {
    testFunctions,
    testFiles: testFiles.length,
    migrations: pyModules(join(backend, 'alembic', 'versions')).length,
    routeModules: pyModules(join(backend, 'app', 'routes')).length,
    serviceModules: pyModules(join(backend, 'app', 'services')).length,
  };
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const webApp = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  const stats = collectRepoStats(resolve(webApp, '..'));
  const out = join(webApp, 'src', 'data', 'repo-stats.json');
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, JSON.stringify(stats, null, 2) + '\n');
  console.log('repo-stats:', stats);
}
