import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// jsdom has no SVG geometry (getTotalLength), so real GSAP MotionPath would throw in tests.
vi.mock('gsap', () => ({
  gsap: {
    registerPlugin: vi.fn(),
    timeline: vi.fn(() => ({ to: vi.fn().mockReturnThis(), kill: vi.fn() })),
    context: vi.fn(() => ({ revert: vi.fn() })),
    fromTo: vi.fn(),
  },
}));
vi.mock('gsap/MotionPathPlugin', () => ({ MotionPathPlugin: {} }));
vi.mock('gsap/ScrollTrigger', () => ({ ScrollTrigger: {} }));

if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}
