import { describe, expect, it } from "vitest";

import { breadcrumbsFor } from "./breadcrumbs";
import { filterCommands, navigationCommands, type Command } from "./commands";
import { NAV_GROUPS } from "./nav";

const COMMANDS: Command[] = [
  { id: "a", label: "Request logs", group: "Observe", to: "/logs" },
  { id: "b", label: "Audit log", group: "Observe", to: "/audit" },
  { id: "c", label: "Policy", group: "Govern", to: "/policy" },
  { id: "d", label: "API keys", group: "Govern", to: "/api-keys" },
  { id: "e", label: "Provider keys", group: "Connect", to: "/provider-keys" },
  { id: "f", label: "Users and roles", group: "Admin", to: "/users-roles" },
];

const ids = (list: Command[]) => list.map((c) => c.id);

describe("navigationCommands", () => {
  it("has one command per sidebar item, in sidebar order, each with its route and group", () => {
    const commands = navigationCommands();
    expect(commands.map((c) => c.to)).toEqual(NAV_GROUPS.flatMap((g) => g.items.map((i) => i.to)));
    expect(commands[0]).toMatchObject({ group: "Observe", to: "/" });
    expect(new Set(commands.map((c) => c.id)).size).toBe(commands.length);
  });
});

describe("filterCommands", () => {
  it("returns everything, in order, for an empty or blank query", () => {
    expect(filterCommands(COMMANDS, "")).toBe(COMMANDS);
    expect(filterCommands(COMMANDS, "   ")).toBe(COMMANDS);
  });

  it("ranks a label that starts with the word above one that merely contains it", () => {
    // "key" starts "API keys" only as a later word, and "Provider keys" the same; both rank after exact starts
    expect(ids(filterCommands(COMMANDS, "log"))).toEqual(["a", "b"]); // "Request logs" (word start) then "Audit log" (word start); stable order
    expect(ids(filterCommands(COMMANDS, "pol"))[0]).toBe("c");
    expect(ids(filterCommands(COMMANDS, "au"))[0]).toBe("b");
  });

  it("matches on the group, so a group name finds its pages", () => {
    expect(ids(filterCommands(COMMANDS, "govern"))).toEqual(["c", "d"]);
  });

  it("requires every word to match", () => {
    expect(ids(filterCommands(COMMANDS, "provider keys"))).toEqual(["e"]);
    expect(ids(filterCommands(COMMANDS, "keys govern"))).toEqual(["d"]);
    expect(filterCommands(COMMANDS, "keys nonsense")).toEqual([]);
  });

  it("ignores case and surrounding space, and finds nothing for a miss", () => {
    expect(ids(filterCommands(COMMANDS, "  POLICY "))).toEqual(["c"]);
    expect(filterCommands(COMMANDS, "zzz")).toEqual([]);
  });

  it("matches a word after a separator", () => {
    expect(ids(filterCommands(COMMANDS, "roles"))).toEqual(["f"]); // "Users and roles"
  });
});

describe("breadcrumbsFor", () => {
  it("is group then page for a sidebar page, with the page as the current item", () => {
    expect(breadcrumbsFor("/policy")).toEqual([{ label: "Govern" }, { label: "Policy" }]);
    expect(breadcrumbsFor("/")).toEqual([{ label: "Observe" }, { label: "Dashboard" }]);
  });

  it("adds the sub-page for a request trace, linking back to the list", () => {
    expect(breadcrumbsFor("/logs/abc-123")).toEqual([{ label: "Observe" }, { label: "Request logs", to: "/logs" }, { label: "Request trace" }]);
  });

  it("tolerates a trailing slash", () => {
    expect(breadcrumbsFor("/policy/")).toEqual([{ label: "Govern" }, { label: "Policy" }]);
  });

  it("does not let / match everything, and gives nothing for an unknown path", () => {
    expect(breadcrumbsFor("/nonsense")).toEqual([]);
    expect(breadcrumbsFor("/policyx")).toEqual([]);
  });

  it("falls back to group and page for an unknown child of a known page", () => {
    expect(breadcrumbsFor("/policy/whatever")).toEqual([{ label: "Govern" }, { label: "Policy" }]);
  });

  it("covers every sidebar page", () => {
    for (const group of NAV_GROUPS) {
      for (const item of group.items) {
        expect(breadcrumbsFor(item.to).map((c) => c.label)).toEqual([group.label, item.label]);
      }
    }
  });
});
