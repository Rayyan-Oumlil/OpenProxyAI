import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../state/ThemeContext";
import { ThemeToggle } from "../../components/ui/ThemeToggle";
import { CommandPalette } from "./CommandPalette";
import { NAV_GROUPS } from "./nav";

const logout = vi.fn();
vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ logout }) }));

function Where() {
  return <p data-testid="where">{useLocation().pathname}</p>;
}

function Harness({ startOpen = true }: { startOpen?: boolean }) {
  const [open, setOpen] = useState(startOpen);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        reopen
      </button>
      <CommandPalette open={open} onOpenChange={setOpen} />
      <Routes>
        <Route path="*" element={<Where />} />
      </Routes>
    </>
  );
}

function renderPalette(startOpen = true) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={["/"]}>
        <Harness startOpen={startOpen} />
        <ThemeToggle />
      </MemoryRouter>
    </ThemeProvider>,
  );
}

const input = () => screen.getByRole("combobox", { name: "Go to page or action" }) as HTMLInputElement;
const options = () => within(screen.getByRole("listbox", { name: "Results" })).getAllByRole("option");
const THEME_COMMANDS = 3;
const pageCount = NAV_GROUPS.reduce((sum, g) => sum + g.items.length, 0) + THEME_COMMANDS;

beforeEach(() => {
  logout.mockReset();
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});
afterEach(cleanup);

describe("CommandPalette", () => {
  it("renders nothing while closed", () => {
    renderPalette(false);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("lists every page and Sign out, as a combobox over a listbox with the first option highlighted", async () => {
    renderPalette();
    expect(await screen.findByRole("dialog", { name: "Command palette" })).toBeTruthy();
    expect(options()).toHaveLength(pageCount + 1);
    expect(options()[0].getAttribute("aria-selected")).toBe("true");
    expect(input().getAttribute("aria-controls")).toBe(screen.getByRole("listbox").id);
    expect(input().getAttribute("aria-activedescendant")).toBe(options()[0].id);
  });

  it("filters as you type, and says when nothing matches", async () => {
    renderPalette();
    await screen.findByRole("dialog");
    expect(options().map((o) => o.textContent)).toEqual(["PolicyGovern", "Policy pluginsGovern"]);
    expect(options().map((o) => o.textContent)).toEqual(["PolicyGovern"]);

    fireEvent.change(input(), { target: { value: "zzz" } });
    expect(screen.queryAllByRole("option")).toHaveLength(0);
    expect(screen.getByText(/Nothing matches "zzz"/)).toBeTruthy();
    expect(input().hasAttribute("aria-activedescendant")).toBe(false);
  });

  it("moves the highlight with the arrow keys and wraps around at both ends", async () => {
    renderPalette();
    await screen.findByRole("dialog");
    fireEvent.keyDown(input(), { key: "ArrowDown" });
    expect(options()[1].getAttribute("aria-selected")).toBe("true");
    expect(input().getAttribute("aria-activedescendant")).toBe(options()[1].id);

    fireEvent.keyDown(input(), { key: "ArrowUp" });
    fireEvent.keyDown(input(), { key: "ArrowUp" }); // from the first option, wraps to the last
    expect(options().at(-1)!.getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(input(), { key: "ArrowDown" }); // and back to the first
    expect(options()[0].getAttribute("aria-selected")).toBe("true");
  });

  it("opens the highlighted page on Enter and closes", async () => {
    renderPalette();
    await screen.findByRole("dialog");
    fireEvent.change(input(), { target: { value: "audit" } });
    fireEvent.keyDown(input(), { key: "Enter" });
    expect(screen.getByTestId("where").textContent).toBe("/audit");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("opens a page on click", async () => {
    renderPalette();
    await screen.findByRole("dialog");
    fireEvent.click(screen.getByRole("option", { name: /Provider health/ }));
    expect(screen.getByTestId("where").textContent).toBe("/provider-health");
  });

  it("signs out from the palette", async () => {
    renderPalette();
    await screen.findByRole("dialog");
    fireEvent.change(input(), { target: { value: "sign out" } });
    fireEvent.keyDown(input(), { key: "Enter" });
    expect(logout).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("where").textContent).toBe("/"); // no navigation
  });

  it("does nothing on Enter when there are no results", async () => {
    renderPalette();
    await screen.findByRole("dialog");
    fireEvent.change(input(), { target: { value: "zzz" } });
    fireEvent.keyDown(input(), { key: "Enter" });
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByTestId("where").textContent).toBe("/");
  });

  it("switches the theme from the keyboard, and the sidebar toggle follows", async () => {
    renderPalette();
    await screen.findByRole("dialog");
    fireEvent.change(input(), { target: { value: "dark" } });
    expect(options().map((o) => o.textContent)).toEqual(["Theme: DarkAppearance"]);
    fireEvent.keyDown(input(), { key: "Enter" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(screen.getByRole("radio", { name: "Dark" }).getAttribute("aria-checked")).toBe("true");
    expect(window.localStorage.getItem("opai-theme")).toBe("dark");
  });

  it("closes on Escape and starts fresh when reopened", async () => {
    renderPalette();
    await screen.findByRole("dialog");
    fireEvent.change(input(), { target: { value: "policy" } });
    fireEvent.keyDown(input(), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    fireEvent.click(screen.getByRole("button", { name: "reopen" }));
    await screen.findByRole("dialog");
    expect(input().value).toBe("");
    expect(options()).toHaveLength(pageCount + 1);
  });
});
