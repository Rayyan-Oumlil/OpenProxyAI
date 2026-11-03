import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DataTable, type Column } from "./DataTable";

interface Row {
  id: string;
  name: string;
  cost: number;
}

const ROWS: Row[] = [
  { id: "a", name: "gpt-4o", cost: 12.5 },
  { id: "b", name: "claude", cost: 3 },
];

const COLUMNS: Column<Row>[] = [
  { key: "name", header: "Model", mono: true, cell: (row) => row.name },
  { key: "cost", header: "Cost", align: "right", cell: (row) => `$${row.cost}` },
];

const EMPTY = { title: "No models yet", detail: "Send a request to see it here." };

function renderTable(props: Partial<React.ComponentProps<typeof DataTable<Row>>> = {}) {
  return render(<DataTable caption="Models" columns={COLUMNS} rows={ROWS} getRowId={(row) => row.id} empty={EMPTY} {...props} />);
}

afterEach(cleanup);

describe("DataTable", () => {
  it("renders headers, rows and an accessible name", () => {
    renderTable();
    expect(screen.getByRole("table", { name: "Models" })).not.toBeNull();
    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Model", "Cost"]);
    expect(screen.getByText("gpt-4o")).not.toBeNull();
    expect(screen.getByText("$12.5").className).toContain("dt__right");
  });

  it("shows skeleton rows, marked busy, while loading", () => {
    const { container } = renderTable({ rows: undefined, isLoading: true, skeletonRows: 4 });
    expect(screen.getByRole("table", { hidden: true }).getAttribute("aria-busy")).toBe("true");
    expect(container.querySelectorAll(".dt__skeleton-row")).toHaveLength(4);
    expect(screen.queryByText("No models yet")).toBeNull();
  });

  it("explains an empty table instead of drawing an empty grid", () => {
    renderTable({ rows: [] });
    expect(screen.getByText("No models yet")).not.toBeNull();
    expect(screen.getByText("Send a request to see it here.")).not.toBeNull();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("does not call a loading table empty", () => {
    renderTable({ rows: [], isLoading: true });
    expect(screen.queryByText("No models yet")).toBeNull();
  });

  it("announces errors and offers a retry", () => {
    const onRetry = vi.fn();
    renderTable({ error: { title: "Could not load models", detail: "The server did not respond.", onRetry } });
    expect(screen.getByRole("alert").textContent).toContain("Could not load models");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("omits the retry button when there is nothing to retry", () => {
    renderTable({ error: { title: "Forbidden", detail: "Only admins can see this." } });
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("makes rows clickable and keyboard operable when asked", () => {
    const onRowClick = vi.fn();
    renderTable({ onRowClick });
    const row = screen.getByText("gpt-4o").closest("tr")!;
    expect(row.getAttribute("tabindex")).toBe("0");
    fireEvent.click(row);
    fireEvent.keyDown(row, { key: "Enter" });
    fireEvent.keyDown(row, { key: " " });
    fireEvent.keyDown(row, { key: "a" });
    expect(onRowClick).toHaveBeenCalledTimes(3);
    expect(onRowClick).toHaveBeenCalledWith(ROWS[0]);
  });

  it("leaves rows alone when no handler is given", () => {
    renderTable();
    expect(screen.getByText("gpt-4o").closest("tr")!.getAttribute("tabindex")).toBeNull();
  });

  it("lets a page mark some rows as not interactive", () => {
    renderTable({ onRowClick: vi.fn(), isRowInteractive: (row) => row.id === "a" });
    expect(screen.getByText("gpt-4o").closest("tr")!.getAttribute("tabindex")).toBe("0");
    expect(screen.getByText("claude").closest("tr")!.getAttribute("tabindex")).toBeNull();
  });

  it("does not hijack key presses inside the row", () => {
    const onRowClick = vi.fn();
    renderTable({ onRowClick, columns: [{ key: "x", header: "X", cell: () => <button type="button">Copy</button> }] });
    fireEvent.keyDown(screen.getAllByRole("button", { name: "Copy" })[0], { key: "Enter" });
    expect(onRowClick).not.toHaveBeenCalled();
  });

  it("expands one row and reports it with aria-expanded", () => {
    renderTable({ onRowClick: vi.fn(), expandedId: "a", renderExpanded: (row) => <p>Detail for {row.name}</p> });
    expect(screen.getByText("Detail for gpt-4o")).not.toBeNull();
    expect(screen.queryByText("Detail for claude")).toBeNull();
    expect(screen.getByText("gpt-4o").closest("tr")!.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("claude").closest("tr")!.getAttribute("aria-expanded")).toBe("false");
  });

  it("renders a footer under the rows", () => {
    renderTable({ footer: <span>2 of 2</span> });
    expect(screen.getByText("2 of 2")).not.toBeNull();
  });

  it("supports a compact density", () => {
    const { container } = renderTable({ density: "compact" });
    expect(container.querySelector(".dt--compact")).not.toBeNull();
  });
});
