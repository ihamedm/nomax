import { useEffect } from "react";

/**
 * Per-route document head for the public pages.
 *
 * The app is a client-rendered SPA, so Google sees these tags after it runs the
 * bundle. Social crawlers that never run JS only get the defaults in
 * `index.html`: proper link previews need server-side rendering, which this
 * stack does not have.
 */
export const SITE_NAME = "نومکس";
export const DEFAULT_DESCRIPTION = "نومکس؛ بازار محلی معرفی کسب‌وکارها و خدمات شهر بهبهان";

export interface SeoOptions {
  title: string;
  description?: string;
  /** Canonical path, e.g. `/businesses/kafe-stare`. */
  path: string;
  image?: string | null;
  /** Search queries and pending businesses must stay out of the index. */
  noindex?: boolean;
  jsonLd?: Record<string, unknown>[];
}

export function absoluteUrl(path: string): string {
  return new URL(path, window.location.origin).href;
}

function setMeta(attr: "name" | "property", key: string, content: string | null | undefined) {
  let tag = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`);
  if (!content) {
    tag?.remove();
    return;
  }
  if (!tag) {
    tag = document.createElement("meta");
    tag.setAttribute(attr, key);
    document.head.appendChild(tag);
  }
  tag.content = content;
}

function setLink(rel: string, href: string) {
  let link = document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`);
  if (!link) {
    link = document.createElement("link");
    link.rel = rel;
    document.head.appendChild(link);
  }
  link.href = href;
}

/** Applies the head tags now; returns a cleanup for the JSON-LD blocks. */
export function applySeo({
  title,
  description = DEFAULT_DESCRIPTION,
  path,
  image,
  noindex = false,
  jsonLd = [],
}: SeoOptions): () => void {
  const url = absoluteUrl(path);
  const imageUrl = image ? (image.startsWith("http") ? image : absoluteUrl(image)) : null;

  document.title = title;
  setMeta("name", "description", description);
  setMeta("name", "robots", noindex ? "noindex, follow" : "index, follow");
  setMeta("property", "og:type", "website");
  setMeta("property", "og:site_name", SITE_NAME);
  setMeta("property", "og:locale", "fa_IR");
  setMeta("property", "og:title", title);
  setMeta("property", "og:description", description);
  setMeta("property", "og:url", url);
  setMeta("property", "og:image", imageUrl);
  setMeta("name", "twitter:card", imageUrl ? "summary_large_image" : "summary");
  setMeta("name", "twitter:title", title);
  setMeta("name", "twitter:description", description);
  setMeta("name", "twitter:image", imageUrl);
  setLink("canonical", url);

  // Replace the previous route's graph so a page never stacks schemas.
  document.head.querySelectorAll('script[data-seo-jsonld]').forEach((node) => node.remove());
  const scripts = jsonLd.map((graph) => {
    const script = document.createElement("script");
    script.type = "application/ld+json";
    script.dataset.seoJsonld = "true";
    script.textContent = JSON.stringify(graph);
    document.head.appendChild(script);
    return script;
  });
  return () => scripts.forEach((script) => script.remove());
}

export function useSeo(options: SeoOptions) {
  // The options object is rebuilt every render; compare by value instead.
  const key = JSON.stringify(options);
  useEffect(() => {
    const applied = JSON.parse(key) as SeoOptions;
    return applySeo(applied);
  }, [key]);
}
