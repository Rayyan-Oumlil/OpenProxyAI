import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RouteErrorBoundary } from "./RouteErrorBoundary";

afterEach(cleanup);

function Boom(): never {
  throw new Error("kaboom");
}

describe("RouteErrorBoundary", () => {
  it("shows what failed instead of a blank screen, and keeps content outside it alive", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(
      <div>
        <nav>navigation</nav>
        <RouteErrorBoundary resetKey="/billing">
          <Boom />
        </RouteErrorBoundary>
      </div>,
    );
    expect(screen.getByRole("alert").textContent).toContain("Something went wrong on this page");
    expect(screen.getByRole("alert").textContent).toContain("kaboom");
    expect(screen.getByText("navigation")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reload page" })).toBeTruthy();
    spy.mockRestore();
  });

  it("renders its children when nothing fails", () => {
    render(
      <RouteErrorBoundary resetKey="/ok">
        <p>fine</p>
      </RouteErrorBoundary>,
    );
    expect(screen.getByText("fine")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("recovers when the person navigates to another page", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const { rerender } = render(
      <RouteErrorBoundary resetKey="/billing">
        <Boom />
      </RouteErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toBeTruthy();

    rerender(
      <RouteErrorBoundary resetKey="/logs">
        <p>logs page</p>
      </RouteErrorBoundary>,
    );
    expect(screen.getByText("logs page")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
    spy.mockRestore();
  });
});
