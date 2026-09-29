import { render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ControlMap from './ControlMap';
import { SCENES } from './scenes';

// gsap is mocked globally in src/test/setup.ts.

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

function setReducedMotion(reduced: boolean) {
  vi.spyOn(window, 'matchMedia').mockImplementation((q: string) => ({
    matches: reduced && q.includes('reduce'), media: q, onchange: null,
    addListener: () => {}, removeListener: () => {}, addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false,
  }));
}

describe('useMapAnimation', () => {
  it('emits no events when reduced motion is requested', async () => {
    setReducedMotion(true);
    vi.useFakeTimers();
    const onEvent = vi.fn();
    render(<ControlMap scene={SCENES.home} onEvent={onEvent} />);
    await vi.advanceTimersByTimeAsync(5000);
    expect(onEvent).not.toHaveBeenCalled();
  });

  it('emits events when motion is allowed', async () => {
    setReducedMotion(false);
    vi.useFakeTimers();
    const onEvent = vi.fn();
    render(<ControlMap scene={SCENES.home} onEvent={onEvent} />);
    await vi.advanceTimersByTimeAsync(5000);
    expect(onEvent).toHaveBeenCalled();
  });

  it('keeps live packets bounded after a long run', async () => {
    setReducedMotion(false);
    vi.useFakeTimers();
    const { container } = render(<ControlMap scene={SCENES.home} />);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(container.querySelectorAll('[data-layer="packets"] circle').length).toBeLessThanOrEqual(24);
  });
});
