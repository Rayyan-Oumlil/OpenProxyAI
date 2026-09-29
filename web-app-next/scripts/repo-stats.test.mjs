// @vitest-environment node
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { collectRepoStats } from './repo-stats.mjs';

function fixture() {
  const root = mkdtempSync(join(tmpdir(), 'repo-stats-'));
  const b = join(root, 'backend');
  for (const d of ['tests', 'alembic/versions', 'app/routes', 'app/services']) mkdirSync(join(b, d), { recursive: true });
  writeFileSync(join(b, 'tests', 'test_a.py'), 'def test_one():\n    pass\n\nasync def test_two():\n    pass\n\ndef helper():\n    pass\n');
  writeFileSync(join(b, 'tests', 'test_b.py'), 'class TestX:\n    def test_three(self):\n        pass\n');
  writeFileSync(join(b, 'tests', 'conftest.py'), 'def test_not_counted_file():\n    pass\n');
  writeFileSync(join(b, 'tests', '__init__.py'), '');
  writeFileSync(join(b, 'alembic/versions', 'abc_first.py'), '');
  writeFileSync(join(b, 'alembic/versions', 'def_second.py'), '');
  writeFileSync(join(b, 'app/routes', '__init__.py'), '');
  writeFileSync(join(b, 'app/routes', 'proxy.py'), '');
  writeFileSync(join(b, 'app/services', 'llm_service.py'), '');
  writeFileSync(join(b, 'app/services', 'cache_service.py'), '');
  writeFileSync(join(b, 'app/services', 'notes.txt'), '');
  return root;
}

describe('collectRepoStats', () => {
  it('counts tests, migrations and modules', () => {
    expect(collectRepoStats(fixture())).toEqual({
      testFunctions: 3,
      testFiles: 2,
      migrations: 2,
      routeModules: 1,
      serviceModules: 2,
    });
  });

  it('fails loudly when the backend is not checked out', () => {
    const empty = mkdtempSync(join(tmpdir(), 'repo-stats-empty-'));
    expect(() => collectRepoStats(empty)).toThrow(/missing .*backend.*tests/);
  });

  it('committed repo-stats.json matches the real repo', () => {
    const repoRoot = resolve(__dirname, '..', '..');
    const committed = JSON.parse(readFileSync(resolve(__dirname, '..', 'src', 'data', 'repo-stats.json'), 'utf8'));
    expect(committed).toEqual(collectRepoStats(repoRoot));
  });
});
