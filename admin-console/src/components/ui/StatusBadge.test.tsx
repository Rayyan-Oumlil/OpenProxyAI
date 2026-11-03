import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { StatusBadge, verdictForPolicyAction, type Verdict } from "./StatusBadge";

afterEach(cleanup);

describe("StatusBadge", () => {
  it.each<[Verdict, string]>([
    ["allowed", "Allowed"],
    ["flagged", "Flagged"],
    ["blocked", "Blocked"],
    ["drifted", "Drifted"],
    ["pending", "Pending"],
    ["neutral", "None"],
  ])("labels %s as %s so the state never depends on colour", (verdict, label) => {
    render(<StatusBadge verdict={verdict} />);
    expect(screen.getByText(label).getAttribute("data-verdict")).toBe(verdict);
  });

  it("gives every verdict its own glyph shape", () => {
    const shapes = (["allowed", "flagged", "blocked", "drifted", "pending", "neutral"] as Verdict[]).map((verdict) => {
      const { container, unmount } = render(<StatusBadge verdict={verdict} />);
      const svg = container.querySelector("svg")!;
      const signature = svg.innerHTML;
      expect(svg.getAttribute("aria-hidden")).toBe("true");
      unmount();
      return signature;
    });
    expect(new Set(shapes).size).toBe(shapes.length);
  });

  it("accepts custom text", () => {
    render(<StatusBadge verdict="blocked">PII found</StatusBadge>);
    expect(screen.getByText("PII found")).not.toBeNull();
  });
});

describe("verdictForPolicyAction", () => {
  it("maps the API's policy actions", () => {
    expect(verdictForPolicyAction("allow")).toBe("allowed");
    expect(verdictForPolicyAction("log_only")).toBe("flagged");
    expect(verdictForPolicyAction("redact")).toBe("flagged");
    expect(verdictForPolicyAction("block")).toBe("blocked");
    expect(verdictForPolicyAction(null)).toBe("neutral");
    expect(verdictForPolicyAction("something-new")).toBe("neutral");
  });
});
