import { NAV_GROUPS } from "./nav";

export interface Command {
  id: string;
  label: string;
  /** Shown beside the label and searched too, so "govern" finds Policy and API keys. */
  group: string;
  /** Route to open. A command without one is an action the palette runs itself. */
  to?: string;
}

/** Every page in the sidebar, in sidebar order. */
export function navigationCommands(): Command[] {
  return NAV_GROUPS.flatMap((group) => group.items.map((item) => ({ id: `go:${item.to}`, label: item.label, group: group.label, to: item.to })));
}

/** Lower is better: the label starts with the word, a label word starts with it, the label contains it, only the group does. */
function rank(command: Command, token: string): number | null {
  const label = command.label.toLowerCase();
  if (label.startsWith(token)) return 0;
  if (label.split(/[\s&/-]+/).some((word) => word.startsWith(token))) return 1;
  if (label.includes(token)) return 2;
  if (command.group.toLowerCase().includes(token)) return 3;
  return null;
}

/**
 * Every word of the query must match something; commands are ordered by their worst word's rank, then by
 * their original order, so an empty query lists everything as the sidebar does and results are stable.
 */
export function filterCommands(commands: Command[], query: string): Command[] {
  const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return commands;
  const scored: { command: Command; score: number; index: number }[] = [];
  commands.forEach((command, index) => {
    const ranks = tokens.map((token) => rank(command, token));
    if (ranks.some((r) => r === null)) return;
    scored.push({ command, score: Math.max(...(ranks as number[])), index });
  });
  return scored.sort((a, b) => a.score - b.score || a.index - b.index).map((entry) => entry.command);
}
