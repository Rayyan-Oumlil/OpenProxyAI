/** Words for routing decisions, shared by the request trace and the policy preview so they always agree. */

/** Why a registry model was ruled out for a request (the codes come from the gateway's routing rules). */
export const EXCLUSION_TEXT: Record<string, string> = {
  disabled: "the model is disabled",
  no_key: "no provider key is attached",
  key_inactive: "its provider key is inactive",
  class_too_low: "it is not cleared for this data class",
  region: "it does not run in this organization's region",
  risk: "it is above the organization's risk ceiling",
  not_allowed_by_policy: "it is not on the policy allowlist",
};

export interface RoutingOutcome {
  requested: string;
  /** The model chosen, or null when none was authorized. */
  model: string | null;
  reason: string;
}

/** One sentence: what routing did with the request and why. */
export function routingOutcome(r: RoutingOutcome): string {
  if (r.reason === "authorized") return `Served by ${r.model}`;
  if (r.reason === "capability") return `Chose ${r.model} for ${r.requested}`;
  if (r.reason === "not_in_registry") return `${r.requested} is not in the model registry`;
  if (r.reason === "no_model_with_capability") return `No authorized model has the capability in ${r.requested}`;
  if (r.reason.startsWith("not_authorized:")) {
    const code = r.reason.slice("not_authorized:".length);
    return `${r.requested} is not authorized: ${EXCLUSION_TEXT[code] ?? code}`;
  }
  return r.reason;
}
