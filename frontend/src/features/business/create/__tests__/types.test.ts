import { describe, expect, it } from "vitest";

import { instagramId, validateStep, type WizardData } from "../types";

describe("instagramId", () => {
  it("keeps only the id from ids, handles and profile URLs", () => {
    expect(instagramId("nomax.ir")).toBe("nomax.ir");
    expect(instagramId("@nomax.ir")).toBe("nomax.ir");
    expect(instagramId("https://instagram.com/nomax.ir")).toBe("nomax.ir");
    expect(instagramId("https://www.instagram.com/nomax.ir/?hl=en")).toBe("nomax.ir");
    expect(instagramId("instagram.com/nomax.ir/")).toBe("nomax.ir");
  });
});

describe("validateStep step 2", () => {
  const base: WizardData = {
    title: "کافه نومکس",
    description: "توضیح کافی برای این کسب‌وکار",
    category: null,
    subcategory: null,
    address: "بهبهان، خیابان اصلی",
    is24h: false,
    geo: null,
    photos: [],
    intro: "",
    shopPhone: "",
    instagram: "",
    licenseEnabled: false,
    licenseNumber: "",
    licenseImage: "",
    standardTags: [],
    customTags: [],
  };

  it("requires both license fields when the license is checked", () => {
    expect(validateStep(2, { ...base, licenseEnabled: true }, false)).toMatch(/شناسه پروانه/);
    expect(
      validateStep(2, { ...base, licenseEnabled: true, licenseNumber: "123" }, false),
    ).toMatch(/تصویر پروانه/);
    expect(
      validateStep(2, {
        ...base,
        licenseEnabled: true,
        licenseNumber: "123",
        licenseImage: "https://example.com/a.jpg",
      }, false),
    ).toBeNull();
    expect(validateStep(2, base, false)).toBeNull();
  });
});
