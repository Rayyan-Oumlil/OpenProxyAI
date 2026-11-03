import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { sparklinePoints } from "../charts/Sparkline";
import { KpiCard, deltaTone } from "./KpiCard";

afterEach(cleanup);

describe("deltaTone", () => {
  it("judges a change by which direction is good news", () => {
    expect(deltaTone(0.2, "down")).toBe("bad"); // cost went up
    expect(deltaTone(-0.2, "down")).toBe("good"); // cost went down
    expect(deltaTone(0.2, "up")).toBe("good");
    expect(deltaTone(-0.2, "up")).toBe("bad");
  });

  it("is neutral for volume metrics and for changes too small to mean anything", () => {
    expect(deltaTone(0.5, "neutral")).toBe("flat");
    expect(deltaTone(0.0001, "down")).toBe("flat");
  });
});

describe("KpiCard", () => {
  it("shows the value, the change and its baseline, readable without colour", () => {
    render(<KpiCard label="Cost" value="$12.00" delta={0.25} deltaLabel="vs previous 7 days" goodWhen="down" />);
    expect(screen.getByText("Cost")).toBeTruthy();
    expect(screen.getByText("$12.00")).toBeTruthy();
    const delta = document.querySelector(".kpi__delta") as HTMLElement;
    expect(delta.textContent).toContain("Up");
    expect(delta.textContent).toContain("25.0%");
    expect(delta.textContent).toContain("vs previous 7 days");
    expect(delta.className).toContain("kpi__delta--bad");
  });

  it("says when there is no previous period, instead of showing a fake delta", () => {
    render(<KpiCard label="Requests" value="10" delta={null} deltaLabel="vs previous 90 days" />);
    expect(screen.getByText("No previous period to compare")).toBeTruthy();
  });

  it("shows nothing for a delta when the card has no comparison at all", () => {
    render(<KpiCard label="Success rate" value="99%" />);
    expect(document.querySelector(".kpi__delta")).toBeNull();
  });

  it("calls a tiny change 'no change'", () => {
    render(<KpiCard label="Requests" value="10" delta={0.0001} deltaLabel="vs previous 7 days" />);
    expect(screen.getByText(/no change/i)).toBeTruthy();
  });

  it("draws a sparkline only when there are at least two points", () => {
    const { rerender } = render(<KpiCard label="Requests" value="10" series={[1]} />);
    expect(document.querySelector("svg")).toBeNull();
    rerender(<KpiCard label="Requests" value="10" series={[1, 2, 3]} />);
    expect(document.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });
});

describe("sparklinePoints", () => {
  it("scales values into the box, low at the bottom and high at the top", () => {
    const [low, high] = sparklinePoints([0, 10]).split(" ").map((p) => Number(p.split(",")[1]));
    expect(low).toBeGreaterThan(high);
  });

  it("draws a level line for a flat series and nothing for no data, never NaN", () => {
    const flat = sparklinePoints([5, 5, 5]);
    expect(flat).not.toContain("NaN");
    expect(new Set(flat.split(" ").map((p) => p.split(",")[1])).size).toBe(1);
    expect(sparklinePoints([])).toBe("");
    expect(sparklinePoints([7])).not.toContain("NaN");
  });
});
