const LOGIN_PATH = "/login";

/**
 * Accept only same-origin, in-app paths as post-login destinations.
 * Rejects absolute URLs (`https://…`), protocol-relative URLs (`//…`) and
 * backslash tricks that browsers normalise into another origin.
 */
export function safeNextPath(value: string | null | undefined): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return null;

  try {
    const base = "https://nomax.invalid";
    const url = new URL(value, base);
    if (url.origin !== base) return null;
    if (url.pathname === LOGIN_PATH) return null;
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return null;
  }
}

/** Build a login URL that returns the user to `next` after a successful login. */
export function loginPath(next?: string | null): string {
  const safe = safeNextPath(next);
  return safe ? `${LOGIN_PATH}?next=${encodeURIComponent(safe)}` : LOGIN_PATH;
}

/** Current path + query, ready to be used as a `next` target. */
export function returnPath(location: { pathname: string; search?: string; hash?: string }): string {
  return `${location.pathname}${location.search ?? ""}${location.hash ?? ""}`;
}

export interface LoginTarget {
  to: string | null;
  state?: { openReview: true };
}

/**
 * Convert the stored `next` destination into a navigation target. The review
 * intent travels in router state (not the URL) so the review sheet can open
 * after login without leaving a reusable `?review=1` link behind.
 */
export function splitLoginTarget(next: string | null | undefined): LoginTarget {
  const safe = safeNextPath(next);
  if (!safe) return { to: null };

  const url = new URL(safe, "https://nomax.invalid");
  if (url.searchParams.get("review") !== "1") return { to: safe };

  url.searchParams.delete("review");
  return {
    to: `${url.pathname}${url.search}${url.hash}`,
    state: { openReview: true },
  };
}
