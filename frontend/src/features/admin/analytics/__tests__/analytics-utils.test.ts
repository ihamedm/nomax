import { describe, expect, it } from "vitest";

import {
  formatDuration,
  marketStatusMeta,
  roleEmoji,
  shortDateLabel,
} from "../analytics-utils";

describe("formatDuration", () => {
  it("handles missing values", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(undefined)).toBe("—");
  });

  it("formats seconds, minutes, hours and days", () => {
    expect(formatDuration(30)).toBe("۳۰ ثانیه");
    expect(formatDuration(90)).toBe("۲ دقیقه");
    expect(formatDuration(2 * 60 * 60)).toBe("۲ ساعت");
    expect(formatDuration(2 * 24 * 60 * 60)).toBe("۲ روز");
  });
});

describe("market status", () => {
  it("maps verbose labels", () => {
    expect(marketStatusMeta("urgent").label).toBe("جذب فوری");
    expect(marketStatusMeta("shortage").label).toBe("کمبود عرضه");
    expect(marketStatusMeta("balanced").label).toBe("متعادل");
  });
});

describe("role and date labels", () => {
  it("returns role emoji and a Persian short date", () => {
    expect(roleEmoji("owner")).toBe("🏪");
    expect(roleEmoji("unknown")).toBe("👤");
    expect(shortDateLabel("2026-10-31")).not.toBe("");
  });
});
