import type { Coordinates } from "@/types";

/**
 * Browser geolocation behind a promise. Kept outside features so a Capacitor
 * shell can replace it with a native implementation later.
 */
export function getCurrentPosition(): Promise<Coordinates> {
  return new Promise((resolve, reject) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      reject(new Error("geolocation_unavailable"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        });
      },
      (error) => reject(error),
      {
        enableHighAccuracy: true,
        timeout: 12_000,
        maximumAge: 60_000,
      },
    );
  });
}

/**
 * True when the browser has not already granted geolocation, so a manual
 * location action should show the explainer sheet instead of a silent failure.
 */
export async function geolocationNeedsPrompt(): Promise<boolean> {
  try {
    const status = await navigator.permissions?.query({
      name: "geolocation" as PermissionName,
    });
    return status?.state !== "granted";
  } catch {
    return true;
  }
}
