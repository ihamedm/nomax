import { afterEach, describe, expect, it, vi } from "vitest";

import { navigationHref } from "@/stores/navigation";

function userAgent(value: string) {
  vi.spyOn(window.navigator, "userAgent", "get").mockReturnValue(value);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("navigationHref", () => {
  it("opens the Neshan app through an Android package intent with a store fallback", () => {
    userAgent("Mozilla/5.0 (Linux; Android 14; Pixel 8)");
    const href = navigationHref("neshan", 30.6, 50.8);
    expect(href).toContain("intent://nshn.ir/?destination=30.6,50.8");
    expect(href).toContain("package=org.rajman.neshan.traffic.tehran.navigator");
    expect(href).toContain("play.google.com");
  });

  it("uses the Neshan URI scheme on iOS", () => {
    userAgent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)");
    expect(navigationHref("neshan", 30.6, 50.8)).toBe(
      "neshan://?destination=30.6,50.8",
    );
  });

  it("falls back to the Neshan web map on desktop", () => {
    userAgent("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0)");
    expect(navigationHref("neshan", 30.6, 50.8)).toBe(
      "https://neshan.org/maps/share/30.6,50.8",
    );
  });

  it("builds Google Maps and Balad links", () => {
    expect(navigationHref("google", 30.6, 50.8)).toBe(
      "https://www.google.com/maps/dir/?api=1&destination=30.6,50.8",
    );
    expect(navigationHref("balad", 30.6, 50.8)).toBe(
      "https://balad.ir/location?latitude=30.6&longitude=50.8",
    );
  });
});
