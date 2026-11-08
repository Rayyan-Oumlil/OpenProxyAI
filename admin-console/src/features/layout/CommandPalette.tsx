import * as Dialog from "@radix-ui/react-dialog";
import { CornerDownLeft, Search } from "lucide-react";
import { useId, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { cn } from "../../lib/utils";
import { useAuth } from "../../state/AuthContext";
import { useTheme } from "../../state/ThemeContext";
import { filterCommands, navigationCommands, themeCommands, type Command } from "./commands";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Jump to any page (or sign out) from the keyboard. The input is a combobox over a listbox: focus stays in
 * the input and `aria-activedescendant` names the highlighted option, so a screen reader follows the arrows.
 */
export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const { setMode } = useTheme();
  const listId = useId();
  const opener = useRef<HTMLElement | null>(null);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  const commands = useMemo<Command[]>(() => [...navigationCommands(), ...themeCommands(), { id: "sign-out", label: "Sign out", group: "Account" }], []);
  const results = useMemo(() => filterCommands(commands, query), [commands, query]);
  const highlighted = Math.min(active, Math.max(results.length - 1, 0));

  function close() {
    onOpenChange(false);
    setQuery("");
    setActive(0);
  }

  function run(command: Command) {
    close();
    if (command.to) navigate(command.to);
    else if (command.theme) setMode(command.theme);
    else if (command.id === "sign-out") logout();
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive(results.length === 0 ? 0 : (highlighted + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive(results.length === 0 ? 0 : (highlighted - 1 + results.length) % results.length);
    } else if (event.key === "Enter" && results[highlighted]) {
      event.preventDefault();
      run(results[highlighted]);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={(next) => (next ? onOpenChange(true) : close())}>
      <Dialog.Portal>
        <Dialog.Overlay className="drawer-scrim" />
        <Dialog.Content
          className="palette"
          aria-describedby={undefined}
          // Ctrl+K has no trigger element for Radix to return focus to, so remember who had it and give it back.
          onOpenAutoFocus={() => {
            opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
          }}
          onCloseAutoFocus={(event) => {
            if (opener.current?.isConnected) {
              event.preventDefault();
              opener.current.focus();
            }
          }}
        >
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <div className="palette__field">
            <Search size={16} aria-hidden="true" />
            <input
              role="combobox"
              aria-expanded="true"
              aria-controls={listId}
              aria-activedescendant={results[highlighted] ? `${listId}-${highlighted}` : undefined}
              aria-label="Go to page or action"
              className="palette__input"
              placeholder="Go to…"
              value={query}
              autoComplete="off"
              spellCheck={false}
              onChange={(event) => {
                setQuery(event.target.value);
                setActive(0);
              }}
              onKeyDown={onKeyDown}
            />
          </div>
          <ul id={listId} role="listbox" aria-label="Results" className="palette__list">
            {results.map((command, index) => (
              <li
                key={command.id}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === highlighted}
                className={cn("palette__item", index === highlighted && "is-active")}
                onMouseEnter={() => setActive(index)}
                onClick={() => run(command)}
              >
                <span>{command.label}</span>
                <span className="palette__group">{command.group}</span>
              </li>
            ))}
            {results.length === 0 ? (
              <li role="presentation" className="palette__empty">
                Nothing matches "{query}".
              </li>
            ) : null}
          </ul>
          <p className="palette__hint" aria-hidden="true">
            <CornerDownLeft size={12} /> to open · ↑↓ to move · esc to close
          </p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
