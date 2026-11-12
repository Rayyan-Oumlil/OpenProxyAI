import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PolicyConfigRequest } from "../../api/types";
import { withSetting } from "../../lib/behavior";
import { BehaviorTab } from "./BehaviorTab";

afterEach(cleanup);

/** Holds the form the way the Policy page does, and exposes the latest value to assertions. */
function Harness({ initial, isAdmin = true, spy }: { initial: PolicyConfigRequest; isAdmin?: boolean; spy: (form: PolicyConfigRequest) => void }) {
  const [form, setForm] = useState(initial);
  spy(form);
  return <BehaviorTab form={form} setForm={(update) => setForm(update)} isAdmin={isAdmin} />;
}

function renderTab(initial: PolicyConfigRequest = {}, isAdmin = true) {
  const latest = vi.fn();
  render(<Harness initial={initial} isAdmin={isAdmin} spy={latest} />);
  return { form: () => latest.mock.calls.at(-1)![0] as PolicyConfigRequest };
}

describe("BehaviorTab", () => {
  it("offers defaults with citations and a ceiling without", () => {
    renderTab();
    expect(screen.getAllByLabelText(/^Creativity/)).toHaveLength(2);
    expect(screen.getAllByLabelText(/^Response length/)).toHaveLength(2);
    expect(screen.getAllByLabelText(/Ask for citations/)).toHaveLength(1); // a ceiling cannot hold citations
  });

  it("shows what is stored", () => {
    renderTab({ behavior_defaults: { creativity: "low", citations: true }, behavior_ceiling: { max_response_length: "short" } });
    const creativity = screen.getAllByLabelText(/^Creativity/) as HTMLSelectElement[];
    expect(creativity[0].value).toBe("low");
    expect(creativity[1].value).toBe("");
    expect((screen.getByLabelText(/Ask for citations/) as HTMLInputElement).checked).toBe(true);
  });

  it("writes a ceiling and clears it again, sending an object with no empty entries", () => {
    const { form } = renderTab();
    const ceilingCreativity = screen.getAllByLabelText(/^Creativity/)[1];
    fireEvent.change(ceilingCreativity, { target: { value: "low" } });
    expect(form().behavior_ceiling).toEqual({ creativity: "low" });
    fireEvent.change(ceilingCreativity, { target: { value: "" } });
    expect(form().behavior_ceiling).toEqual({});
  });

  it("is read-only for a non-admin", () => {
    renderTab({}, false);
    for (const el of screen.getAllByRole("combobox")) expect((el as HTMLSelectElement).disabled).toBe(true);
    expect((screen.getByLabelText(/Ask for citations/) as HTMLInputElement).disabled).toBe(true);
  });

  it("says plainly that a ceiling also lowers raw parameters", () => {
    renderTab();
    expect(screen.getByText(/a raw parameter cannot walk around it/)).toBeTruthy();
  });
});

describe("withSetting", () => {
  it("sets, replaces and removes without touching the input", () => {
    const base = { creativity: "low" as const };
    expect(withSetting(base, "reasoning_depth", "high")).toEqual({ creativity: "low", reasoning_depth: "high" });
    expect(withSetting(base, "creativity", "")).toEqual({});
    expect(withSetting(base, "citations", undefined)).toEqual({ creativity: "low" });
    expect(base).toEqual({ creativity: "low" });
  });
});
