export const PRIVATE_TAG = "private";

/** "Q3  review, Ops" -> ["Q3 review", "Ops"]. The server lower-cases, de-duplicates and has the final say on what is valid. */
export function parseTags(input: string): string[] {
  return input
    .split(",")
    .map((t) => t.trim().replace(/ {2,}/g, " "))
    .filter(Boolean);
}

export function hasPrivateTag(tags: readonly string[]): boolean {
  return tags.some((t) => t.toLowerCase() === PRIVATE_TAG);
}

/** The tags without the quick "private" one, for the free-text field (the checkbox owns that one). */
export function withoutPrivate(tags: readonly string[]): string[] {
  return tags.filter((t) => t.toLowerCase() !== PRIVATE_TAG);
}

/** Free-text tags plus the "private" tag when it is switched on. */
export function composeTags(typed: string, keepPrivate: boolean): string[] {
  const list = withoutPrivate(parseTags(typed));
  return keepPrivate ? [...list, PRIVATE_TAG] : list;
}
