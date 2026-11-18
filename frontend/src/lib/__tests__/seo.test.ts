import { afterEach, describe, expect, it } from "vitest";

import { absoluteUrl, applySeo } from "@/lib/seo";

afterEach(() => {
  document.head.innerHTML = "";
});

describe("seo", () => {
  it("writes the title, description, canonical and social tags", () => {
    applySeo({
      title: "کافه ستاره | رستوران در بهبهان | نومکس",
      description: "قهوه و صبحانه",
      path: "/businesses/kafe-stare",
      image: "/uploads/cover.jpg",
      jsonLd: [{ "@type": "LocalBusiness", name: "کافه ستاره" }],
    });

    expect(document.title).toBe("کافه ستاره | رستوران در بهبهان | نومکس");
    expect(document.querySelector('meta[name="description"]')?.getAttribute("content")).toBe(
      "قهوه و صبحانه",
    );
    expect(document.querySelector('link[rel="canonical"]')?.getAttribute("href")).toBe(
      absoluteUrl("/businesses/kafe-stare"),
    );
    expect(document.querySelector('meta[property="og:url"]')?.getAttribute("content")).toBe(
      absoluteUrl("/businesses/kafe-stare"),
    );
    expect(document.querySelector('meta[property="og:image"]')?.getAttribute("content")).toBe(
      absoluteUrl("/uploads/cover.jpg"),
    );
    expect(document.querySelectorAll('script[data-seo-jsonld]')).toHaveLength(1);
  });

  it("replaces the previous page graph and can mark a page noindex", () => {
    applySeo({ title: "خانه", path: "/", jsonLd: [{ "@type": "WebSite" }] });
    const cleanup = applySeo({
      title: "جستجو",
      path: "/search",
      noindex: true,
      jsonLd: [{ "@type": "ItemList" }, { "@type": "BreadcrumbList" }],
    });

    expect(document.querySelectorAll('script[data-seo-jsonld]')).toHaveLength(2);
    expect(document.querySelector('meta[name="robots"]')?.getAttribute("content")).toBe(
      "noindex, follow",
    );

    cleanup();
    expect(document.querySelectorAll('script[data-seo-jsonld]')).toHaveLength(0);
  });
});
