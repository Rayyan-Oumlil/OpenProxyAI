/**
 * Decode the `exp` field from a JWT payload using base64url decoding.
 * No external library — the payload is standard base64url-encoded JSON.
 * Returns the expiry as a Unix timestamp in seconds, or null on any failure.
 */
export function decodeJwtExp(token: string): number | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;

    // base64url → base64 → JSON
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = atob(base64);
    const payload = JSON.parse(json) as Record<string, unknown>;

    const exp = payload["exp"];
    return typeof exp === "number" ? exp : null;
  } catch {
    return null;
  }
}
