import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider, useConfirm } from "./ConfirmDialog";

afterEach(cleanup);

function Harness({ onResult, destructive = true }: { onResult: (ok: boolean) => void; destructive?: boolean }) {
  const confirm = useConfirm();
  return (
    <button
      type="button"
      onClick={async () =>
        onResult(await confirm({ title: "Delete key?", description: "This cannot be undone.", confirmLabel: "Delete key", destructive }))
      }
    >
      open
    </button>
  );
}

function setup(props: Partial<Parameters<typeof Harness>[0]> = {}) {
  const onResult = vi.fn();
  render(
    <ConfirmProvider>
      <Harness onResult={onResult} {...props} />
    </ConfirmProvider>,
  );
  return onResult;
}

describe("ConfirmDialog", () => {
  it("shows the question and resolves true when confirmed", async () => {
    const onResult = setup();
    fireEvent.click(screen.getByText("open"));

    expect(await screen.findByRole("dialog", { name: "Delete key?" })).toBeTruthy();
    expect(screen.getByText("This cannot be undone.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Delete key" }));

    await vi.waitFor(() => expect(onResult).toHaveBeenCalledWith(true));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("resolves false on Cancel", async () => {
    const onResult = setup();
    fireEvent.click(screen.getByText("open"));
    fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    await vi.waitFor(() => expect(onResult).toHaveBeenCalledWith(false));
  });

  it("resolves false on Escape", async () => {
    const onResult = setup();
    fireEvent.click(screen.getByText("open"));
    const dialog = await screen.findByRole("dialog");
    fireEvent.keyDown(dialog, { key: "Escape" });
    await vi.waitFor(() => expect(onResult).toHaveBeenCalledWith(false));
  });

  it("starts with focus on Cancel so a stray Enter cannot confirm", async () => {
    setup();
    fireEvent.click(screen.getByText("open"));
    const cancel = await screen.findByRole("button", { name: "Cancel" });
    await vi.waitFor(() => expect(document.activeElement).toBe(cancel));
  });

  it("returns focus to the element that opened it", async () => {
    setup();
    const opener = screen.getByText("open");
    opener.focus();
    fireEvent.click(opener);
    fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    await vi.waitFor(() => expect(document.activeElement).toBe(opener));
  });

  it("styles destructive confirmations as dangerous and others as normal", async () => {
    setup({ destructive: true });
    fireEvent.click(screen.getByText("open"));
    expect((await screen.findByRole("button", { name: "Delete key" })).className).toContain("btn-danger");
    cleanup();

    setup({ destructive: false });
    fireEvent.click(screen.getByText("open"));
    expect((await screen.findByRole("button", { name: "Delete key" })).className).not.toContain("btn-danger");
  });

  it("settles an open question as false when a new one replaces it", async () => {
    const results: boolean[] = [];
    function Twice() {
      const confirm = useConfirm();
      return (
        <button
          type="button"
          onClick={() => {
            void confirm({ title: "First?", description: "a" }).then((ok) => results.push(ok));
            void confirm({ title: "Second?", description: "b" }).then((ok) => results.push(ok));
          }}
        >
          twice
        </button>
      );
    }
    render(
      <ConfirmProvider>
        <Twice />
      </ConfirmProvider>,
    );
    fireEvent.click(screen.getByText("twice"));
    expect(await screen.findByRole("dialog", { name: "Second?" })).toBeTruthy();
    await vi.waitFor(() => expect(results).toEqual([false]));
  });

  it("settles an open question as false when the provider unmounts", async () => {
    const onResult = vi.fn();
    const { unmount } = render(
      <ConfirmProvider>
        <Harness onResult={onResult} />
      </ConfirmProvider>,
    );
    fireEvent.click(screen.getByText("open"));
    await screen.findByRole("dialog");
    await act(async () => unmount());
    await vi.waitFor(() => expect(onResult).toHaveBeenCalledWith(false));
  });

  it("fails loudly when used outside the provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<Harness onResult={vi.fn()} />)).toThrow("useConfirm must be used inside <ConfirmProvider>");
    spy.mockRestore();
  });
});
