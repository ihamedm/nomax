import { describe, expect, it } from "vitest";

import { compressImageForUpload, targetDimensions } from "@/lib/image";

describe("targetDimensions", () => {
  it("keeps small images unchanged", () => {
    expect(targetDimensions(800, 600, 1600)).toEqual({ width: 800, height: 600 });
  });

  it("scales the longest side and preserves aspect ratio", () => {
    expect(targetDimensions(3200, 1600, 1600)).toEqual({ width: 1600, height: 800 });
    expect(targetDimensions(1200, 3000, 1500)).toEqual({ width: 600, height: 1500 });
  });

  it("handles degenerate input", () => {
    expect(targetDimensions(0, 300)).toEqual({ width: 0, height: 0 });
  });
});

describe("compressImageForUpload", () => {
  it("passes non-image files through untouched", async () => {
    const file = new File(["hello"], "notes.txt", { type: "text/plain" });
    await expect(compressImageForUpload(file)).resolves.toBe(file);
  });

  it("passes SVGs through because they cannot be canvas-compressed", async () => {
    const file = new File(["<svg/>"], "icon.svg", { type: "image/svg+xml" });
    await expect(compressImageForUpload(file)).resolves.toBe(file);
  });
});
