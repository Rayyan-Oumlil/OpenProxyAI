import type { McpTool } from "./types";

export interface FieldChange {
  field: string;
  approved: string;
  live: string;
}

function show(value: unknown): string {
  if (value === undefined) return "(absent)";
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

/**
 * Top-level fields that differ between the approved snapshot and what the server advertises now.
 * The hash covers the whole tool object, so any field (not just the description) can be the change.
 */
export function changedFields(tool: McpTool): FieldChange[] {
  const approved = tool.approved_snapshot;
  if (!approved) return [];
  const fields = [...new Set([...Object.keys(approved), ...Object.keys(tool.definition)])].sort();
  return fields
    .filter((field) => JSON.stringify(approved[field]) !== JSON.stringify(tool.definition[field]))
    .map((field) => ({ field, approved: show(approved[field]), live: show(tool.definition[field]) }));
}
