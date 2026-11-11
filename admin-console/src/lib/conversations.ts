import type {
  ContextSummary,
  Turn,
  WithheldReason,
} from "../api/conversationTypes";
import { dataClassLabel } from "./dataClasses";

export const REASON_LABEL: Record<WithheldReason, string> = {
  above_clearance: "More sensitive than this model is cleared for",
  over_budget: "Left out to fit the context size",
};

/** "2 earlier messages were not sent to openai/gpt-4o: more sensitive than it is cleared for." Empty when nothing was held back. */
export function withheldNotice(context: ContextSummary): string {
  const count = context.withheld.length;
  if (count === 0) return "";
  const byClearance = context.withheld.filter(
    (w) => w.reason === "above_clearance",
  ).length;
  const byBudget = count - byClearance;
  const parts: string[] = [];
  if (byClearance > 0)
    parts.push(
      `${byClearance} more sensitive than ${context.model} is cleared for`,
    );
  if (byBudget > 0) parts.push(`${byBudget} left out to fit the context size`);
  return `${count} earlier ${count === 1 ? "message was" : "messages were"} not sent to ${context.model}: ${parts.join(", ")}.`;
}

/** The turn a withheld record points at, so the drawer can show what was held back (to people who may read it anyway). */
export function turnBySeq(
  turns: readonly Turn[],
  seq: number,
): Turn | undefined {
  return turns.find((t) => t.seq === seq);
}

/** What the server said, turned into something a person can act on. Unknown messages pass through unchanged. */
export function friendlyError(message: string): string {
  if (message.startsWith("Conversations are not enabled")) {
    return "Conversations are turned off for your organization. An admin can turn them on under Policy, in the Evaluation tab.";
  }
  if (message.startsWith("Another message in this conversation"))
    return "The previous message is still being answered. Try again in a moment.";
  return message;
}

/** "Internal" next to a model in the picker, so the user sees up front which models will not get a confidential history. */
export function modelOptionLabel(modelId: string, maxClass: string): string {
  return `${modelId} (up to ${dataClassLabel(maxClass)})`;
}
