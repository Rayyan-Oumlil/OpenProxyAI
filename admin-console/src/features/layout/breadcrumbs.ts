import { NAV_GROUPS } from "./nav";

export interface Crumb {
  label: string;
  /** Absent for the current page and for the group, which has no page of its own. */
  to?: string;
}

/** Pages that live under a sidebar page and are not in the sidebar themselves. */
const SUBPAGES: Record<string, string> = {
  "/logs": "Request trace",
};

/**
 * Group > page (> sub-page), from the same data as the sidebar so the two cannot disagree.
 * Unknown paths get no breadcrumbs rather than a guess.
 */
export function breadcrumbsFor(pathname: string): Crumb[] {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  let best: { group: string; label: string; to: string } | null = null;
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      const matches = item.to === "/" ? path === "/" : path === item.to || path.startsWith(`${item.to}/`);
      if (matches && (best === null || item.to.length > best.to.length)) best = { group: group.label, label: item.label, to: item.to };
    }
  }
  if (!best) return [];

  const sub = path !== best.to ? SUBPAGES[best.to] : undefined;
  if (path !== best.to && !sub) return [{ label: best.group }, { label: best.label }];
  return sub
    ? [{ label: best.group }, { label: best.label, to: best.to }, { label: sub }]
    : [{ label: best.group }, { label: best.label }];
}
