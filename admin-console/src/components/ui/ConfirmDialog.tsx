import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "./dialog";

export interface ConfirmOptions {
  title: string;
  description: string;
  /** Defaults to "Confirm". Name the action ("Delete key"), not "OK". */
  confirmLabel?: string;
  /** Destructive actions get the danger style. */
  destructive?: boolean;
}

type Confirm = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<Confirm | null>(null);

interface Pending {
  options: ConfirmOptions;
  resolve: (confirmed: boolean) => void;
}

/**
 * Replaces window.confirm: a real dialog with a focus trap, Escape to cancel, focus returned to the
 * trigger, and focus starting on Cancel so a stray Enter cannot confirm a destructive action.
 */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null);
  const cancelButton = useRef<HTMLButtonElement>(null);
  const current = useRef<Pending | null>(null);
  const opener = useRef<HTMLElement | null>(null);

  const settle = useCallback((confirmed: boolean) => {
    current.current?.resolve(confirmed);
    current.current = null;
    setPending(null);
  }, []);

  const confirm = useCallback<Confirm>((options) => {
    // A second request while one is open cancels the first rather than leaving it hanging.
    current.current?.resolve(false);
    // Opened from code, not a Radix trigger, so remember who asked and give focus back on close.
    if (!current.current) opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    return new Promise<boolean>((resolve) => {
      const next = { options, resolve };
      current.current = next;
      setPending(next);
    });
  }, []);

  // An unmount with a dialog open must not leave the caller awaiting forever.
  useEffect(() => () => current.current?.resolve(false), []);

  const value = useMemo(() => confirm, [confirm]);

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      <Dialog open={pending !== null} onOpenChange={(open) => (open ? undefined : settle(false))}>
        <DialogContent
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            cancelButton.current?.focus();
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            opener.current?.focus();
          }}
        >
          <DialogHeader>
            <DialogTitle>{pending?.options.title}</DialogTitle>
            <DialogDescription>{pending?.options.description}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button type="button" ref={cancelButton} className="btn-outline" onClick={() => settle(false)}>
              Cancel
            </button>
            <button
              type="button"
              className={pending?.options.destructive ? "btn-danger" : "bg-accent-sky"}
              onClick={() => settle(true)}
            >
              {pending?.options.confirmLabel ?? "Confirm"}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): Confirm {
  const confirm = useContext(ConfirmContext);
  if (!confirm) throw new Error("useConfirm must be used inside <ConfirmProvider>");
  return confirm;
}
