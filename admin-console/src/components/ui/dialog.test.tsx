import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./dialog";

function Harness({ onCloseAutoFocus }: { onCloseAutoFocus?: (e: Event) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Open it
      </button>
      {open ? (
        <Dialog open onOpenChange={(o) => (o ? undefined : setOpen(false))}>
          <DialogContent onCloseAutoFocus={onCloseAutoFocus}>
            <DialogHeader>
              <DialogTitle>A dialog</DialogTitle>
              <DialogDescription>Opened by a plain button</DialogDescription>
            </DialogHeader>
          </DialogContent>
        </Dialog>
      ) : null}
    </>
  );
}

afterEach(cleanup);

describe("DialogContent focus", () => {
  it("returns focus to the button that opened it, even without a Radix trigger", async () => {
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "Open it" });
    opener.focus();
    fireEvent.click(opener);
    await screen.findByRole("dialog", { name: "A dialog" });
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });

  it("lets a dialog take over where focus goes by preventing the default itself", async () => {
    let elsewhere: HTMLElement | null = null;
    render(
      <>
        <button type="button" ref={(el) => (elsewhere = el)}>
          Somewhere else
        </button>
        <Harness onCloseAutoFocus={(e) => { e.preventDefault(); elsewhere?.focus(); }} />
      </>,
    );
    const opener = screen.getByRole("button", { name: "Open it" });
    opener.focus();
    fireEvent.click(opener);
    await screen.findByRole("dialog");
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    await waitFor(() => expect(document.activeElement).toBe(elsewhere));
  });
});
