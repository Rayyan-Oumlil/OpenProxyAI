import { Monitor, Moon, Sun } from "lucide-react";

import { cn } from "../../lib/utils";
import { THEME_MODES, type ThemeMode } from "../../lib/theme";
import { useTheme } from "../../state/ThemeContext";

const OPTIONS: Record<ThemeMode, { label: string; Icon: typeof Sun }> = {
  system: { label: "Match system", Icon: Monitor },
  dark: { label: "Dark", Icon: Moon },
  light: { label: "Light", Icon: Sun },
};

/** A three-way radio group: it is a choice among themes, not an on/off switch. */
export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { mode, setMode } = useTheme();
  return (
    <div className={cn("theme-toggle", compact && "theme-toggle--compact")} role="radiogroup" aria-label="Color theme">
      {THEME_MODES.map((value) => {
        const { label, Icon } = OPTIONS[value];
        const selected = mode === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={selected}
            title={label}
            className={cn("theme-toggle__option", selected && "is-selected")}
            onClick={() => setMode(value)}
          >
            <Icon size={14} aria-hidden="true" />
            <span className="sr-only">{label}</span>
          </button>
        );
      })}
    </div>
  );
}
