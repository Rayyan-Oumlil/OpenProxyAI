import { render, screen } from '@testing-library/react';
import { createRoutesStub } from 'react-router';
import { describe, expect, it } from 'vitest';
import HomeRoute from './home';
import stats from '../data/repo-stats.json';

function renderHome() {
  const Stub = createRoutesStub([{ path: '/', Component: HomeRoute }]);
  return render(<Stub initialEntries={['/']} />);
}

describe('home', () => {
  it('leads with the positioning line', () => {
    renderHome();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('The control plane for enterprise AI');
  });

  it('walks through all seven pipeline stages', () => {
    renderHome();
    for (const s of ['Authenticate', 'Rate limit', 'Policy', 'Cache', 'Route', 'Upstream', 'Log']) {
      expect(screen.getByRole('heading', { name: new RegExp(s) })).toBeInTheDocument();
    }
  });

  it('shows the drop-in code swap and real repo stats', () => {
    renderHome();
    expect(screen.getAllByText(/base_url|baseURL/).length).toBeGreaterThan(0);
    expect(screen.getByText(String(stats.testFunctions))).toBeInTheDocument();
  });
});
