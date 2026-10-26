/**
 * Platform boundary. Anything that differs between the web build, a future
 * Capacitor shell, or an Android native wrapper belongs here so feature code
 * never branches on the platform directly.
 */
export const APP_ENV =
  import.meta.env.VITE_APP_ENV ?? (import.meta.env.DEV ? "local" : "production");

export const isLocal = APP_ENV === "local";

export const isNativeShell =
  typeof window !== "undefined" && "Capacitor" in (window as unknown as Record<string, unknown>);

export const appVersion = "0.1.0";

export const platform = {
  kind: isNativeShell ? ("native" as const) : ("web" as const),
  appVersion,
  isLocal,
};
