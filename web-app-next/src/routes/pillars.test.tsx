import { render, screen, within } from '@testing-library/react';
import { createRoutesStub } from 'react-router';
import { describe, expect, it } from 'vitest';
import { capabilitiesFor } from '../data/capabilities';
import AgentsRoute from './agents';
import FinopsRoute from './finops';
import ModelsRoute from './models';
import TrustRoute from './trust';

const PAGES = [
  { path: '/models', Component: ModelsRoute, pillar: 'models' },
  { path: '/agents', Component: AgentsRoute, pillar: 'agents' },
  { path: '/trust', Component: TrustRoute, pillar: 'trust' },
  { path: '/finops', Component: FinopsRoute, pillar: 'finops' },
] as const;

describe.each(PAGES)('$path', ({ path, Component, pillar }) => {
  function renderPage() {
    const Stub = createRoutesStub([{ path, Component }]);
    return render(<Stub initialEntries={[path]} />);
  }

  it('has one h1 and lists every capability for the pillar', () => {
    renderPage();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    for (const c of capabilitiesFor(pillar)) expect(screen.getByRole('heading', { name: c.title })).toBeInTheDocument();
  });

  it('links built capabilities to their source, and only those', () => {
    renderPage();
    for (const c of capabilitiesFor(pillar)) {
      const card = screen.getByRole('heading', { name: c.title }).closest('li');
      if (!card) throw new Error(`no card for ${c.id}`);
      const link = within(card).queryByRole('link', { name: /view source/i });
      if (c.status === 'built') expect(link).toHaveAttribute('href', expect.stringContaining(c.source));
      else expect(link).toBeNull();
    }
  });
});

it('trust page includes both live demos', () => {
  const Stub = createRoutesStub([{ path: '/trust', Component: TrustRoute }]);
  render(<Stub initialEntries={['/trust']} />);
  expect(screen.getByLabelText(/your prompt/i)).toBeInTheDocument();
  expect(screen.getByText(/hashing/i)).toBeInTheDocument();
});
