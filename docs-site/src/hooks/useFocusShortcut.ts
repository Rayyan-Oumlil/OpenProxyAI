import {useEffect, type RefObject} from 'react';

/** Ctrl+K (Cmd+K on a Mac) moves focus to the given input. */
export function useFocusShortcut(target: RefObject<HTMLInputElement | null>): void {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent): void {
      if (event.key.toLowerCase() !== 'k' || !(event.ctrlKey || event.metaKey)) {
        return;
      }
      const input = target.current;
      // A hidden input (the sidebar on a phone) leaves the browser's own shortcut alone.
      if (!input || input.offsetParent === null) {
        return;
      }
      event.preventDefault();
      input.focus();
      input.select();
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [target]);
}
