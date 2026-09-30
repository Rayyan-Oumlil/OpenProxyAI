import { render, screen } from '@testing-library/react';
import { createRoutesStub } from 'react-router';
import { describe, expect, it } from 'vitest';
import { PLANS } from '../data/pricing';
import PricingRoute from './pricing';
import NotFoundRoute from './not-found';

describe('pricing', () => {
  it('renders every plan with its price', () => {
    const Stub = createRoutesStub([{ path: '/pricing', Component: PricingRoute }]);
    render(<Stub initialEntries={['/pricing']} />);
    for (const p of PLANS) {
      expect(screen.getByRole('heading', { name: p.name })).toBeInTheDocument();
      expect(screen.getByText(p.price)).toBeInTheDocument();
    }
  });

  it('mirrors backend PLAN_FEATURES limits', () => {
    const byId = Object.fromEntries(PLANS.map(p => [p.id, p]));
    expect(byId.free.users).toBe('3 users');
    expect(byId.starter.users).toBe('50 users');
    expect(byId.growth.users).toBe('200 users');
    expect(byId.enterprise.users).toBe('Unlimited users');
    expect([byId.free.retention, byId.starter.retention, byId.growth.retention, byId.enterprise.retention])
      .toEqual(['7-day audit retention', '30-day audit retention', '90-day audit retention', '365-day audit retention']);
  });
});

describe('not found', () => {
  it('links back home', () => {
    const Stub = createRoutesStub([{ path: '*', Component: NotFoundRoute }]);
    render(<Stub initialEntries={['/nope']} />);
    expect(screen.getByRole('link', { name: /back to the control plane/i })).toHaveAttribute('href', '/');
  });
});
