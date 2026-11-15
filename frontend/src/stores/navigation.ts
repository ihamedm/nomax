import { create } from "zustand";

export type NavigationApp = "neshan" | "google" | "balad";

export const NAVIGATION_APPS: Array<{ value: NavigationApp; label: string }> = [
  { value: "neshan", label: "نشان" },
  { value: "google", label: "گوگل مپ" },
  { value: "balad", label: "بلد" },
];

const STORAGE_KEY = "nomax-navigation-app";

// Play Store id of the Neshan app, used by the Android intent fallback.
const NESHAN_ANDROID_PACKAGE = "org.rajman.neshan.traffic.tehran.navigator";

function storedApp(): NavigationApp {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value === "google" || value === "balad" || value === "neshan" ? value : "neshan";
  } catch {
    return "neshan";
  }
}

function userAgentMatches(pattern: RegExp): boolean {
  return typeof navigator !== "undefined" && pattern.test(navigator.userAgent);
}

/** Where the routing button should go for the selected app. */
export function navigationHref(app: NavigationApp, lat: number, lng: number): string {
  const coords = `${lat},${lng}`;
  if (app === "google") {
    return `https://www.google.com/maps/dir/?api=1&destination=${coords}`;
  }
  if (app === "balad") {
    return `https://balad.ir/location?latitude=${lat}&longitude=${lng}`;
  }
  if (userAgentMatches(/Android/i)) {
    // Package-targeted intent: opens Neshan when installed, otherwise the
    // Play Store page (Android's install prompt).
    const store = encodeURIComponent(
      `https://play.google.com/store/apps/details?id=${NESHAN_ANDROID_PACKAGE}`,
    );
    return `intent://nshn.ir/?destination=${coords}#Intent;scheme=https;package=${NESHAN_ANDROID_PACKAGE};S.browser_fallback_url=${store};end`;
  }
  if (userAgentMatches(/iPhone|iPad|iPod/i)) {
    return `neshan://?destination=${coords}`;
  }
  return `https://neshan.org/maps/share/${coords}`;
}

interface NavigationState {
  app: NavigationApp;
  setApp: (app: NavigationApp) => void;
}

export const useNavigationApp = create<NavigationState>((set) => ({
  app: storedApp(),

  setApp(app) {
    try {
      window.localStorage.setItem(STORAGE_KEY, app);
    } catch {
      // The choice still applies for this session when storage is unavailable.
    }
    set({ app });
  },
}));
