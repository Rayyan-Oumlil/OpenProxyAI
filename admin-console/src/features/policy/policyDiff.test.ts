import { describe, expect, it } from "vitest";

import type { PolicyConfigRequest } from "../../api/types";
import { changedPolicyFields } from "./policyDiff";

const saved: PolicyConfigRequest = {
  enforcement_mode: "enforce",
  allowed_models: ["gpt-4o"],
  blocked_keywords: ["project-phoenix"],
  pii_detection_enabled: true,
  data_class_map: { ssn: "confidential" },
  model_rate_limits: {},
};

describe("changedPolicyFields", () => {
  it("is empty when nothing changed", () => {
    expect(changedPolicyFields(saved, { ...saved })).toEqual({});
  });

  it("returns only what changed, so an unchanged setting is never resent", () => {
    const form = { ...saved, enforcement_mode: "log_only" as const };
    expect(changedPolicyFields(saved, form)).toEqual({ enforcement_mode: "log_only" });
  });

  it("sees a changed list and a changed map", () => {
    const form = { ...saved, blocked_keywords: ["project-phoenix", "x"], data_class_map: { ssn: "secret" as const } };
    expect(changedPolicyFields(saved, form)).toEqual({ blocked_keywords: ["project-phoenix", "x"], data_class_map: { ssn: "secret" } });
  });

  it("sends an emptied list, because clearing a setting is a change", () => {
    expect(changedPolicyFields(saved, { ...saved, allowed_models: [] })).toEqual({ allowed_models: [] });
  });

  it("does not mutate its inputs", () => {
    const form = { ...saved, enforcement_mode: "off" as const };
    const before = JSON.stringify([saved, form]);
    changedPolicyFields(saved, form);
    expect(JSON.stringify([saved, form])).toBe(before);
  });
});
