import { useEffect, useState } from "react";

/** Tracks a CSS media query. Reports false where matchMedia does not exist (older test DOMs). */
export function useMediaQuery(query: string): boolean {
  const read = () => (typeof window !== "undefined" && typeof window.matchMedia === "function" ? window.matchMedia(query).matches : false);
  const [matches, setMatches] = useState<boolean>(read);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const list = window.matchMedia(query);
    const onChange = () => setMatches(list.matches);
    onChange();
    list.addEventListener("change", onChange);
    return () => list.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

/** The nav is a pinned rail from this width up and an off-canvas drawer below it. */
export const DESKTOP_QUERY = "(min-width: 1024px)";
