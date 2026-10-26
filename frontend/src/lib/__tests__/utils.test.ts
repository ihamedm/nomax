import { describe, expect, it } from "vitest";

import { isNumericInput, normalizeDigits, toEn, toFa } from "@/lib/digits";
import { formatDistance, formatPhone, fa } from "@/lib/format";
import { formatJalali } from "@/lib/jalali";

describe("digits", () => {
  it("converts to Persian and back", () => {
    expect(toFa("123")).toBe("۱۲۳");
    expect(toEn("۱۲۳")).toBe("123");
    expect(normalizeDigits("۰۹۱۲-۳۴۵")).toBe("0912345");
    expect(isNumericInput("۱۲3")).toBe(true);
    expect(isNumericInput("abc")).toBe(false);
  });
});

describe("format", () => {
  it("formats phone and distance", () => {
    expect(formatPhone("09123456789")).toBe("۰۹۱۲ ۳۴۵ ۶۷۸۹");
    expect(fa(7)).toBe("۷");
    expect(formatDistance(250)).toContain("۲۵۰");
    expect(formatDistance(null)).toBe("");
  });
});

describe("jalali", () => {
  it("formats a date in Persian calendar", () => {
    expect(formatJalali("2026-03-21T12:00:00Z")).toMatch(/[۰-۹]/);
  });
});

describe("jalali extra", () => {
  it("handles invalid and relative dates", async () => {
    const { formatRelative, formatJalaliDateTime } = await import("@/lib/jalali");
    expect(formatJalali("not-a-date")).toBe("");
    expect(formatJalaliDateTime("2026-03-21T12:00:00Z")).toMatch(/[۰-۹]/);
    expect(formatRelative(Date.now()).length).toBeGreaterThan(0);
  });
});
