import type { PolicyConfigRequest } from "../../api/types";

/**
 * The fields of `form` that differ from `saved`. The policy endpoint merges: what is not sent keeps its value.
 * Sending only changes means a save cannot trip a server rule on a setting the admin did not touch (a plan limit on
 * a switch that was already on), and cannot overwrite a setting another admin changed in the meantime.
 */
export function changedPolicyFields(saved: PolicyConfigRequest, form: PolicyConfigRequest): PolicyConfigRequest {
  const changed = Object.entries(form).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(saved[key as keyof PolicyConfigRequest]));
  return Object.fromEntries(changed) as PolicyConfigRequest;
}
