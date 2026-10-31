import { describe, expect, it } from "vitest";

import { formatCountdown, formatToman, isActiveQuote } from "../quote-utils";

const NOW = new Date("2026-01-01T12:00:00Z").getTime();

describe("formatCountdown", () => {
  it("formats hours and minutes", () => {
    const target = new Date(NOW + 2 * 60 * 60 * 1000 + 5 * 60 * 1000).toISOString();
    expect(formatCountdown(target, NOW)).toBe("۲ ساعت و ۵ دقیقه مانده");
  });

  it("formats days", () => {
    const target = new Date(NOW + 26 * 60 * 60 * 1000).toISOString();
    expect(formatCountdown(target, NOW)).toBe("۱ روز و ۲ ساعت مانده");
  });

  it("omits zero-valued parts", () => {
    const oneDay = new Date(NOW + 24 * 60 * 60 * 1000).toISOString();
    expect(formatCountdown(oneDay, NOW)).toBe("۱ روز مانده");
    const twoHours = new Date(NOW + 2 * 60 * 60 * 1000).toISOString();
    expect(formatCountdown(twoHours, NOW)).toBe("۲ ساعت مانده");
  });

  it("returns the expiry message after the deadline", () => {
    const target = new Date(NOW - 1).toISOString();
    expect(formatCountdown(target, NOW)).toBe("مهلت تمام شده");
  });

  it("handles missing and invalid dates", () => {
    expect(formatCountdown(null, NOW)).toBe("");
    expect(formatCountdown("not-a-date", NOW)).toBe("");
  });
});

describe("formatToman", () => {
  it("formats with Persian thousands separators", () => {
    expect(formatToman(2500000)).toContain("۲٬۵۰۰٬۰۰۰");
    expect(formatToman(2500000)).toContain("تومان");
  });

  it("handles unknown prices", () => {
    expect(formatToman(null)).toBe("قیمت نامشخص");
  });
});

describe("isActiveQuote", () => {
  it("rejects non-active and expired quotes", () => {
    expect(isActiveQuote({ status: "accepted", expires_at: null })).toBe(false);
    expect(
      isActiveQuote({
        status: "active",
        expires_at: new Date(Date.now() - 1000).toISOString(),
      }),
    ).toBe(false);
  });

  it("accepts an active quote with a future deadline", () => {
    expect(
      isActiveQuote({
        status: "active",
        expires_at: new Date(Date.now() + 60_000).toISOString(),
      }),
    ).toBe(true);
  });
});
