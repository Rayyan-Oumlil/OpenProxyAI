export type ThemeMode = "system" | "dark" | "light";

export const THEME_STORAGE_KEY = "opai-theme";
export const THEME_MODES: readonly ThemeMode[] = ["system", "dark", "light"];

function isThemeMode(value: unknown): value is ThemeMode {
  return typeof value === "string" && (THEME_MODES as readonly string[]).includes(value);
}

/** Storage can throw (private windows, blocked site data), so every access is guarded. */
export function readStoredTheme(): ThemeMode {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemeMode(stored) ? stored : "system";
  } catch {
    return "system";
  }
}

/** "system" removes the attribute so the prefers-color-scheme rule in tokens.css decides. */
export function applyTheme(mode: ThemeMode): void {
  const root = document.documentElement;
  if (mode === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", mode);
}

export function storeTheme(mode: ThemeMode): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, mode);
  } catch {
    // The choice still applies for this session; it just will not persist.
  }
}
