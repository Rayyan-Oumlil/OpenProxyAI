import { describe, expect, it } from "vitest";

import { dataClassLabel, describeDataClass } from "./dataClasses";
import { routingOutcome } from "./routing";

const base = { requested: "openai/gpt-4o", model: null as string | null };

describe("routingOutcome", () => {
  it.each([
    [{ ...base, model: "m", reason: "authorized" }, "Served by m"],
    [{ ...base, model: "m", reason: "capability", requested: "cap:CODE" }, "Chose m for cap:CODE"],
    [{ ...base, model: "m", reason: "capability_quality", requested: "cap:CODE" }, "Chose m for cap:CODE, the best-rated authorized model"],
    [{ ...base, reason: "not_in_registry" }, "openai/gpt-4o is not in the model registry"],
    [{ ...base, reason: "not_authorized:risk" }, "openai/gpt-4o is not authorized: it is above the organization's risk ceiling"],
    [{ ...base, reason: "not_authorized:new_code" }, "openai/gpt-4o is not authorized: new_code"],
    [{ ...base, reason: "something_else" }, "something_else"],
  ])("%j", (input, expected) => expect(routingOutcome(input)).toBe(expected));
});

describe("data class wording", () => {
  it("describes the class and what set it", () => {
    expect(describeDataClass("confidential", "detected", ["ssn", "email"])).toBe("Confidential (detected: ssn, email)");
    expect(describeDataClass("internal", "default", [])).toBe("Internal (org default)");
  });
  it("shows an unknown class as it came", () => expect(dataClassLabel("top_secret")).toBe("top_secret"));
});
