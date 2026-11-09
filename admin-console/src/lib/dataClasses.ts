import type { DataClass } from "../api/types";

/** Least to most sensitive. The one list every screen uses, so labels and order cannot drift. */
export const DATA_CLASSES: { value: DataClass; label: string }[] = [
  { value: "public", label: "Public" },
  { value: "internal", label: "Internal" },
  { value: "confidential", label: "Confidential" },
  { value: "secret", label: "Secret" },
];

const CLASS_REASON: Record<string, string> = { default: "org default", header: "set by the caller", detected: "detected" };

/** "Confidential (detected: ssn)": a request's class and what set it, for the trace and the preview. */
export function describeDataClass(name: string, source: string, entities: readonly string[]): string {
  const reason = CLASS_REASON[source] ?? source;
  return `${dataClassLabel(name)} (${reason}${entities.length > 0 ? `: ${entities.join(", ")}` : ""})`;
}

/** A class's label; an unknown value (an older or newer server) is shown as it came rather than hidden. */
export function dataClassLabel(value: string): string {
  return DATA_CLASSES.find((c) => c.value === value)?.label ?? value;
}
