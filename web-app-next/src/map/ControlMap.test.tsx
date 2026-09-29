import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ControlMap from './ControlMap';
import TracePanel from './TracePanel';
import { SCENES } from './scenes';
import { generate } from './sim/engine';

describe('ControlMap', () => {
  it('renders every node label and the scene description for assistive tech', () => {
    render(<ControlMap scene={SCENES.home} animate={false} />);
    for (const n of SCENES.home.nodes) expect(screen.getAllByText(n.label).length).toBeGreaterThan(0);
    expect(screen.getByRole('img', { name: SCENES.home.title })).toBeInTheDocument();
    expect(screen.getByText(SCENES.home.description)).toBeInTheDocument();
  });

  it('shows the SIMULATED tag', () => {
    render(<ControlMap scene={SCENES.models} animate={false} />);
    expect(screen.getByText(/simulated/i)).toBeInTheDocument();
  });

  it('renders one path per edge and a packet layer', () => {
    const { container } = render(<ControlMap scene={SCENES.agents} animate={false} />);
    expect(container.querySelectorAll('[data-edge]')).toHaveLength(SCENES.agents.edges.length);
    expect(container.querySelector('[data-layer="packets"]')).not.toBeNull();
  });
});

describe('TracePanel', () => {
  it('shows an empty state before the first packet', () => {
    render(<TracePanel event={null} />);
    expect(screen.getByText(/waiting for traffic/i)).toBeInTheDocument();
  });

  it('shows status, stages and headers of an event', () => {
    const blocked = generate(SCENES.trust, 1, 200).find(e => e.outcome === 'blocked_446');
    if (!blocked) throw new Error('fixture: expected a blocked event in the trust scene');
    render(<TracePanel event={blocked} />);
    expect(screen.getByText('446')).toBeInTheDocument();
    expect(screen.getByText('policy')).toBeInTheDocument();
    expect(screen.getByText('X-OpenProxyAI-Policy-Action')).toBeInTheDocument();
  });
});
