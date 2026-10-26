const SDK_JS = "https://static.neshan.org/sdk/leaflet/v1.9.4/neshan-sdk/v1.0.8/index.js";
const SDK_CSS = "https://static.neshan.org/sdk/leaflet/v1.9.4/neshan-sdk/v1.0.8/index.css";

type LeafletNamespace = Record<string, any>;

let loader: Promise<LeafletNamespace> | null = null;

export function getNeshanKey(): string {
  return (import.meta.env.VITE_NESHAN_MAP_KEY ?? "").trim();
}

function injectStyles(): void {
  if (document.querySelector('link[data-nomax-neshan="true"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = SDK_CSS;
  link.dataset.nomaxNeshan = "true";
  document.head.appendChild(link);
}

/**
 * Loads the Neshan Leaflet SDK once per page. The SDK is an Iranian-hosted
 * runtime dependency and exposes the Leaflet namespace as `window.L`.
 */
export function loadNeshanSdk(): Promise<LeafletNamespace> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("no_window"));
  }

  const globalWindow = window as Window & { L?: LeafletNamespace };
  if (globalWindow.L) return Promise.resolve(globalWindow.L);
  if (loader) return loader;

  loader = new Promise<LeafletNamespace>((resolve, reject) => {
    injectStyles();

    const script = document.createElement("script");
    script.src = SDK_JS;
    script.async = true;
    script.dataset.nomaxNeshan = "true";

    const timer = window.setTimeout(() => {
      script.remove();
      reject(new Error("neshan_sdk_timeout"));
    }, 15_000);

    script.onload = () => {
      window.clearTimeout(timer);
      if (globalWindow.L) resolve(globalWindow.L);
      else reject(new Error("neshan_sdk_missing"));
    };
    script.onerror = () => {
      window.clearTimeout(timer);
      script.remove();
      reject(new Error("neshan_sdk_failed"));
    };

    document.head.appendChild(script);
  }).catch((error: unknown) => {
    loader = null;
    throw error;
  });

  return loader;
}
