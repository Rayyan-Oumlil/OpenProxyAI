import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { render, screen } from '@testing-library/react';
import { createRoutesStub } from 'react-router';
import { describe, expect, it } from 'vitest';
import { CAPABILITIES } from '../data/capabilities';
import { DECISIONS } from '../data/decisions';
import stats from '../data/repo-stats.json';
import EngineeringRoute from './engineering';

function renderPage() {
  const Stub = createRoutesStub([{ path: '/engineering', Component: EngineeringRoute }]);
  return render(<Stub initialEntries={['/engineering']} />);
}

describe('engineering', () => {
  it('shows every repo stat from the generated file', () => {
    renderPage();
    for (const v of Object.values(stats)) expect(screen.getAllByText(String(v)).length).toBeGreaterThan(0);
  });

  it('lists every design decision with a source that exists', () => {
    renderPage();
    expect(DECISIONS.length).toBeGreaterThanOrEqual(4);
    for (const d of DECISIONS) {
      expect(screen.getByRole('heading', { name: d.title })).toBeInTheDocument();
      expect(existsSync(resolve(__dirname, '..', '..', '..', d.source))).toBe(true);
    }
  });

  it('separates what is built from what is next', () => {
    renderPage();
    const built = screen.getByRole('list', { name: /shipped/i });
    const next = screen.getByRole('list', { name: /next/i });
    expect(built.querySelectorAll('li')).toHaveLength(CAPABILITIES.filter(c => c.status === 'built').length);
    expect(next.querySelectorAll('li')).toHaveLength(CAPABILITIES.filter(c => c.status === 'backlog').length);
  });
});
