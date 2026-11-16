import { track } from '@vercel/analytics';

type EventProps = Record<string, string | number | boolean>;

/**
 * Sends a custom event to Vercel Web Analytics. Never throws and never blocks the page:
 * analytics is an observation, not a dependency. Custom events need a Vercel plan that includes
 * them; on other plans the call is a no-op, and page views are still counted.
 */
export function trackEvent(name: string, props?: EventProps): void {
  try {
    track(name, props);
  } catch {
    // Observation only: a failing tracker must never break navigation.
  }
}
