import { beforeEach, describe, expect, it } from "vitest";

import {
  isLocationGranted,
  LOCATION_PROMPT_COOLDOWN_MS,
  LOCATION_PROMPT_LIMIT,
  markLocationGranted,
  recordAutoPrompt,
  shouldAutoPrompt,
} from "@/lib/location-prompt";

const DAY = LOCATION_PROMPT_COOLDOWN_MS;

describe("location prompt schedule", () => {
  beforeEach(() => localStorage.clear());

  it("prompts once per day, at most three times", () => {
    const start = 1_000_000_000_000;
    expect(shouldAutoPrompt(start)).toBe(true);

    recordAutoPrompt(start);
    expect(shouldAutoPrompt(start + 60_000)).toBe(false);

    const second = start + DAY + 1;
    expect(shouldAutoPrompt(second)).toBe(true);
    recordAutoPrompt(second);

    const third = second + DAY + 1;
    expect(shouldAutoPrompt(third)).toBe(true);
    recordAutoPrompt(third);

    expect(shouldAutoPrompt(third + DAY * LOCATION_PROMPT_LIMIT)).toBe(false);
  });

  it("stops asking once permission is granted", () => {
    markLocationGranted();
    expect(isLocationGranted()).toBe(true);
    expect(shouldAutoPrompt(Date.now() + DAY * 10)).toBe(false);
  });

  it("ignores a corrupt saved history", () => {
    localStorage.setItem("nomax.locationPromptShows", "{not json");
    expect(shouldAutoPrompt(Date.now())).toBe(true);
  });
});
