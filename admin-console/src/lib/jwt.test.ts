import { describe, it, expect } from "vitest";
import { decodeJwtExp } from "./jwt";

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none" })).replace(/=/g, "");
  const body = btoa(JSON.stringify(payload))
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
  return `${header}.${body}.sig`;
}

describe("decodeJwtExp", () => {
  it("returns exp from a valid JWT", () => {
    const exp = 1_700_000_000;
    expect(decodeJwtExp(makeJwt({ exp, sub: "user1" }))).toBe(exp);
  });

  it("returns null when exp field is absent", () => {
    expect(decodeJwtExp(makeJwt({ sub: "user1" }))).toBeNull();
  });

  it("returns null when exp is a string", () => {
    expect(decodeJwtExp(makeJwt({ exp: "not-a-number", sub: "user1" }))).toBeNull();
  });

  it("returns null for a token with fewer than 3 parts", () => {
    expect(decodeJwtExp("only.two")).toBeNull();
  });

  it("returns null for a completely invalid token", () => {
    expect(decodeJwtExp("notajwt")).toBeNull();
  });

  it("handles base64url-encoded payloads (- and _ characters)", () => {
    // Force a payload whose base64 encoding contains + and / by using a long string
    const exp = 9_999_999_999;
    const raw = makeJwt({ exp, data: ">>>???!!!" }); // chars that shift base64 output
    expect(decodeJwtExp(raw)).toBe(exp);
  });
});
