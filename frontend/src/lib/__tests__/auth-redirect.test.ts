import { describe, expect, it } from "vitest";

import { loginPath, returnPath, safeNextPath, splitLoginTarget } from "@/lib/auth-redirect";

describe("safeNextPath", () => {
  it("keeps internal paths, query strings and hashes", () => {
    expect(safeNextPath("/businesses/cafe?review=1")).toBe("/businesses/cafe?review=1");
    expect(safeNextPath("/me/reviews#top")).toBe("/me/reviews#top");
    expect(safeNextPath("/")).toBe("/");
  });

  it("rejects external, malformed and login-loop destinations", () => {
    expect(safeNextPath(null)).toBeNull();
    expect(safeNextPath("")).toBeNull();
    expect(safeNextPath("https://example.com")).toBeNull();
    expect(safeNextPath("//example.com/path")).toBeNull();
    expect(safeNextPath("/\\example.com/path")).toBeNull();
    expect(safeNextPath("/login")).toBeNull();
    expect(safeNextPath("/login?next=%2Fme")).toBeNull();
  });
});

describe("loginPath", () => {
  it("encodes the destination and falls back to plain login", () => {
    expect(loginPath("/businesses/cafe?review=1")).toBe(
      "/login?next=%2Fbusinesses%2Fcafe%3Freview%3D1",
    );
    expect(loginPath("https://example.com")).toBe("/login");
    expect(loginPath(null)).toBe("/login");
  });
});

describe("returnPath", () => {
  it("combines pathname, search and hash", () => {
    expect(returnPath({ pathname: "/me/reviews", search: "?page=2", hash: "#list" })).toBe(
      "/me/reviews?page=2#list",
    );
    expect(returnPath({ pathname: "/" })).toBe("/");
  });
});

describe("splitLoginTarget", () => {
  it("moves the review intent into router state and keeps the URL clean", () => {
    expect(splitLoginTarget("/businesses/cafe?review=1")).toEqual({
      to: "/businesses/cafe",
      state: { openReview: true },
    });
    expect(splitLoginTarget("/businesses/cafe?review=1&ref=search")).toEqual({
      to: "/businesses/cafe?ref=search",
      state: { openReview: true },
    });
  });

  it("leaves unrelated destinations untouched", () => {
    expect(splitLoginTarget("/me/reviews?page=2")).toEqual({
      to: "/me/reviews?page=2",
    });
    expect(splitLoginTarget(null)).toEqual({ to: null });
  });
});
