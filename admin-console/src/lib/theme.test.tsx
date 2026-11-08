import { act, cleanup, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeToggle } from "../components/ui/ThemeToggle";
import { ThemeProvider, useTheme } from "../state/ThemeContext";
import { THEME_STORAGE_KEY, applyTheme, readStoredTheme, storeTheme } from "./theme";

const wrapper = ThemeProvider;

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("theme storage", () => {
  it("defaults to following the system", () => {
    expect(readStoredTheme()).toBe("system");
  });

  it("round-trips a saved choice and ignores junk", () => {
    storeTheme("light");
    expect(readStoredTheme()).toBe("light");
    window.localStorage.setItem(THEME_STORAGE_KEY, "sepia");
    expect(readStoredTheme()).toBe("system");
  });

  it("survives storage being blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(readStoredTheme()).toBe("system");
    expect(() => storeTheme("dark")).not.toThrow();
  });
});

describe("applyTheme", () => {
  it("sets the attribute for an explicit choice and clears it for system", () => {
    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    applyTheme("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    applyTheme("system");
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });
});

describe("useTheme", () => {
  it("applies and stores each change", () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    act(() => result.current.setMode("light"));
    expect(result.current.mode).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  });

  it("starts from the saved choice", () => {
    storeTheme("dark");
    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.mode).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });
});

describe("ThemeToggle", () => {
  it("is a radio group with the current theme checked", () => {
    storeTheme("dark");
    render(<ThemeToggle />, { wrapper });
    expect(screen.getByRole("radiogroup", { name: "Color theme" })).not.toBeNull();
    expect(screen.getByRole("radio", { name: "Dark" }).getAttribute("aria-checked")).toBe("true");
    expect(screen.getByRole("radio", { name: "Light" }).getAttribute("aria-checked")).toBe("false");
  });

  it("switches theme on click", () => {
    render(<ThemeToggle />, { wrapper });
    fireEvent.click(screen.getByRole("radio", { name: "Light" }));
    expect(screen.getByRole("radio", { name: "Light" }).getAttribute("aria-checked")).toBe("true");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    fireEvent.click(screen.getByRole("radio", { name: "Match system" }));
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });

  it("throws outside a provider instead of silently using its own state", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => renderHook(() => useTheme())).toThrow(/ThemeProvider/);
  });
});
