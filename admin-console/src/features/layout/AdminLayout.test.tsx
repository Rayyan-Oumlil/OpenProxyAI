import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AdminLayout } from "./AdminLayout";
import { NAV_GROUPS } from "./nav";

vi.mock("../../state/AuthContext", () => ({
  useAuth: () => ({ user: { name: "Ada Admin", email: "ada@example.com", role: "admin" }, logout: vi.fn() }),
}));

function setViewport(desktop: boolean) {
  window.matchMedia = ((query: string) => ({
    matches: desktop && query.includes("min-width: 1024px"),
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
    onchange: null,
  })) as unknown as typeof window.matchMedia;
}

function GoToLogs() {
  const navigate = useNavigate();
  return (
    <button type="button" onClick={() => navigate("/logs")}>
      go to logs
    </button>
  );
}

function renderLayout(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<AdminLayout />}>
          <Route index element={<h1>Dashboard page</h1>} />
          <Route path="logs" element={<h1>Logs page</h1>} />
          <Route path="audit" element={<h1>Audit page</h1>} />
        </Route>
      </Routes>
      <GoToLogs />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(cleanup);

describe("AdminLayout on a wide screen", () => {
  beforeEach(() => setViewport(true));

  it("pins a sidebar with the four groups and every link", () => {
    renderLayout();
    const nav = screen.getByRole("navigation", { name: "Main" });
    for (const group of NAV_GROUPS) {
      expect(within(nav).getByRole("heading", { name: group.label })).not.toBeNull();
      for (const item of group.items) expect(within(nav).getByRole("link", { name: item.label })).not.toBeNull();
    }
    expect(screen.queryByRole("button", { name: "Open navigation" })).toBeNull();
  });

  it("marks the current page for assistive tech", () => {
    renderLayout("/audit");
    expect(screen.getByRole("link", { name: "Audit log" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Dashboard" }).hasAttribute("aria-current")).toBe(false);
  });

  it("offers a skip link to the main landmark", () => {
    renderLayout();
    expect(screen.getByRole("link", { name: "Skip to content" }).getAttribute("href")).toBe("#main-content");
    expect(screen.getByRole("main").id).toBe("main-content");
  });

  it("collapses to icons with the button and with Ctrl+B, keeping accessible names", () => {
    const { container } = renderLayout();
    const shell = container.querySelector(".shell")!;
    expect(shell.getAttribute("data-collapsed")).toBe("false");
    fireEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(shell.getAttribute("data-collapsed")).toBe("true");
    expect(screen.getByRole("link", { name: "Request logs" })).not.toBeNull(); // label is sr-only, not removed
    fireEvent.keyDown(window, { key: "b", ctrlKey: true });
    expect(shell.getAttribute("data-collapsed")).toBe("false");
    expect(window.localStorage.getItem("sidebarCollapsed")).toBe("false");
  });

  it("shows who is signed in", () => {
    renderLayout();
    expect(screen.getByText("Ada Admin")).not.toBeNull();
    expect(screen.getByText("admin")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Sign out" })).not.toBeNull();
  });
});

describe("AdminLayout below 1024px", () => {
  beforeEach(() => setViewport(false));

  it("hides the rail behind a menu button", () => {
    renderLayout();
    expect(screen.queryByRole("navigation", { name: "Main" })).toBeNull();
    const button = screen.getByRole("button", { name: "Open navigation" });
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(button.getAttribute("aria-controls")).toBe("nav-drawer");
  });

  it("opens a modal drawer with the full navigation", () => {
    renderLayout();
    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    const drawer = screen.getByRole("dialog", { name: "Navigation" });
    expect(drawer.id).toBe("nav-drawer");
    expect(within(drawer).getAllByRole("link").length).toBe(NAV_GROUPS.flatMap((g) => g.items).length);
    expect(within(drawer).getByRole("button", { name: "Close navigation" })).not.toBeNull();
  });

  it("closes with Escape", () => {
    renderLayout();
    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("returns focus to the menu button when the drawer closes", async () => {
    renderLayout();
    const menu = screen.getByRole("button", { name: "Open navigation" });
    fireEvent.click(menu);
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    await waitFor(() => expect(document.activeElement).toBe(menu));
  });

  it("closes with the close button", () => {
    renderLayout();
    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    fireEvent.click(screen.getByRole("button", { name: "Close navigation" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("closes itself after you pick a page", () => {
    renderLayout();
    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("link", { name: "Request logs" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("heading", { name: "Logs page" })).not.toBeNull();
  });

  it("closes when the route changes some other way", () => {
    renderLayout();
    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(screen.getByRole("dialog")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "go to logs", hidden: true }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("ignores the Ctrl+B shortcut, which only makes sense for the pinned rail", () => {
    const { container } = renderLayout();
    fireEvent.keyDown(window, { key: "b", ctrlKey: true });
    expect(container.querySelector(".shell")!.getAttribute("data-collapsed")).toBe("false");
  });
});

describe("AdminLayout page bar", () => {
  beforeEach(() => setViewport(true));

  it("shows breadcrumbs for the current page, with the page itself as the current item", () => {
    renderLayout("/audit");
    const crumbs = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(within(crumbs).getByText("Observe")).not.toBeNull();
    expect(within(crumbs).getByText("Audit log").getAttribute("aria-current")).toBe("page");
  });

  it("opens the command palette from the Search button and with Ctrl+K, and Ctrl+K again closes it", async () => {
    renderLayout();
    expect(screen.queryByRole("dialog", { name: "Command palette" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /^Search/ }));
    expect(await screen.findByRole("dialog", { name: "Command palette" })).not.toBeNull();
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Command palette" })).toBeNull());

    fireEvent.keyDown(window, { key: "k", metaKey: true });
    expect(await screen.findByRole("dialog", { name: "Command palette" })).not.toBeNull();
  });

  it("goes to the chosen page from the palette", async () => {
    renderLayout();
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    const box = await screen.findByRole("combobox", { name: "Go to page or action" });
    fireEvent.change(box, { target: { value: "request logs" } });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(await screen.findByRole("heading", { name: "Logs page" })).not.toBeNull();
    expect(within(screen.getByRole("navigation", { name: "Breadcrumb" })).getByText("Request logs")).not.toBeNull();
  });
});
