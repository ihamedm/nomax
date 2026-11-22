import { describe, expect, it } from "vitest";

import { instagramId, validateStep, visibleStandardTags, type WizardData } from "../types";

describe("instagramId", () => {
  it("keeps only the id from ids, handles and profile URLs", () => {
    expect(instagramId("nomax.ir")).toBe("nomax.ir");
    expect(instagramId("@nomax.ir")).toBe("nomax.ir");
    expect(instagramId("https://instagram.com/nomax.ir")).toBe("nomax.ir");
    expect(instagramId("https://www.instagram.com/nomax.ir/?hl=en")).toBe("nomax.ir");
    expect(instagramId("instagram.com/nomax.ir/")).toBe("nomax.ir");
  });
});

describe("visibleStandardTags", () => {
  const subcategory = {
    id: 1,
    category_id: 1,
    slug: "mechanic",
    name: "مکانیک",
    icon: "",
    sort_order: 0,
    standard_tags: ["a", "b", "c", "d", "e", "f", "g", "h"],
    visible_tags: null,
  };

  it("falls back to the first six tags when nothing is configured", () => {
    expect(visibleStandardTags([subcategory])).toEqual(["a", "b", "c", "d", "e", "f"]);
  });

  it("uses the admin subset and de-duplicates across subcategories", () => {
    expect(
      visibleStandardTags([
        { ...subcategory, visible_tags: ["a", "b"] },
        { ...subcategory, id: 2, visible_tags: ["b", "c"] },
      ]),
    ).toEqual(["a", "b", "c"]);
  });

  it("treats an explicit empty subset as nothing visible", () => {
    expect(visibleStandardTags([{ ...subcategory, visible_tags: [] }])).toEqual([]);
  });
});

describe("validateStep step 2", () => {
  const base: WizardData = {
    title: "کافه نومکس",
    description: "توضیح کافی برای این کسب‌وکار",
    category: null,
    subcategories: [],
    address: "بهبهان، خیابان اصلی",
    is24h: false,
    geo: null,
    photos: [],
    avatar: "",
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
