import { useEffect, useRef, useState } from "react";

import { Spinner } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { Coordinates } from "@/types";

import { getNeshanKey, loadNeshanSdk } from "./neshan";

export interface MapMarker {
  id: string;
  lat: number;
  lng: number;
  title?: string;
  subtitle?: string;
  color?: string;
  zIndexOffset?: number;
  offsetX?: number;
  offsetY?: number;
  /** When set, the pin renders as a numbered cluster bubble. */
  count?: number;
  /** Zoom at which this cluster splits into its children. */
  expansionZoom?: number;
  /**
   * Render an individual business as a compact dot. Used at high zoom where
   * hundreds of full-size teardrops would make the map unreadable.
   */
  compact?: boolean;
}

export interface MapViewport {
  zoom: number;
  center: Coordinates;
  bbox: { west: number; south: number; east: number; north: number };
}

interface NeshanMapProps {
  center: Coordinates;
  zoom?: number;
  markers?: MapMarker[];
  className?: string;
  interactive?: boolean;
  fitToMarkers?: boolean;
  /** Fit the city once on mount, then leave camera moves to center/zoom. */
  initialBounds?: [[number, number], [number, number]];
  onMapClick?: (coords: Coordinates) => void;
  onMarkerClick?: (marker: MapMarker) => void;
  /** Fires after pan/zoom so callers can fetch only the visible area. */
  onViewportChange?: (viewport: MapViewport) => void;
  pickerMarker?: Coordinates | null;
  onPickerMove?: (coords: Coordinates) => void;
}

// The Neshan SDK is a UMD Leaflet build; its types live outside our bundle.
type Leaflet = Record<string, any>;

function markerIcon(
  L: Leaflet,
  color: string,
  offsetX = 0,
  offsetY = 0,
) {
  const offsetStyle =
    offsetX || offsetY ? `position:relative;left:${offsetX}px;top:${offsetY}px` : "";
  const offsetAttr = offsetStyle ? ` style="${offsetStyle}"` : "";
  // Every map uses the same teardrop location pin so the tip sits exactly on
  // the point. Picker and feed markers differ only by color.
  return L.divIcon({
    className: "",
    html: `<svg class="nomax-map-pin" viewBox="0 0 24 24" aria-hidden="true"${offsetAttr}><path fill="${color}" stroke="#ffffff" stroke-width="1.1" d="M12 1.7c-4.3 0-7.6 3.3-7.6 7.5 0 5.6 7.6 13.6 7.6 13.6s7.6-8 7.6-13.6c0-4.2-3.3-7.5-7.6-7.5Z"/><circle cx="12" cy="9.1" r="2.85" fill="#ffffff"/></svg>`,
    iconSize: [40, 40],
    iconAnchor: [20, 38],
    popupAnchor: [0, -14],
  });
}

function clusterIcon(L: Leaflet, count: number) {
  // Keep bubbles below the 64 px cluster radius so two neighbouring groups
  // never paint over each other.
  const size = count >= 1000 ? 44 : count >= 100 ? 38 : count >= 10 ? 32 : 28;
  const fontSize = count >= 1000 ? 13 : count >= 100 ? 12 : 11;
  const label = count.toLocaleString("fa-IR");
  return L.divIcon({
    className: "",
    html: `<span class="nomax-map-cluster" style="width:${size}px;height:${size}px;font-size:${fontSize}px">${label}</span>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  });
}

function dotIcon(L: Leaflet, color: string) {
  return L.divIcon({
    className: "",
    html: `<span class="nomax-map-dot" style="background:${color}"></span>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -12],
  });
}

function popupElement(marker: MapMarker): HTMLElement {
  const container = document.createElement("div");
  container.className = "text-right";
  container.dir = "rtl";

  const title = document.createElement("p");
  title.className = "font-bold text-slate-900";
  title.textContent = marker.title ?? "";
  container.appendChild(title);

  if (marker.subtitle) {
    const subtitle = document.createElement("p");
    subtitle.className = "mt-1 text-xs text-slate-500";
    subtitle.textContent = marker.subtitle;
    container.appendChild(subtitle);
  }
  return container;
}

export function NeshanMap({
  center,
  zoom = 13,
  markers = [],
  className,
  interactive = true,
  fitToMarkers = false,
  initialBounds,
  onMapClick,
  onMarkerClick,
  onViewportChange,
  pickerMarker,
  onPickerMove,
}: NeshanMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>(null);
  const layerRef = useRef<any>(null);
  const pickerRef = useRef<any>(null);
  const fittedRef = useRef(false);
  const clickRef = useRef(onMapClick);
  const markerClickRef = useRef(onMarkerClick);
  const pickerMoveRef = useRef(onPickerMove);
  const viewportRef = useRef(onViewportChange);
  const viewportFrame = useRef(0);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  clickRef.current = onMapClick;
  markerClickRef.current = onMarkerClick;
  pickerMoveRef.current = onPickerMove;
  viewportRef.current = onViewportChange;

  const key = getNeshanKey();

  useEffect(() => {
    let cancelled = false;

    if (!key) {
      setError(
        "کلید نقشه در بسته برنامه نیست. VITE_NESHAN_MAP_KEY را تنظیم و برنامه را دوباره بسازید (Docker: docker compose up -d --build web).",
      );
      return;
    }

    setError(null);
    setReady(false);

    loadNeshanSdk()
      .then((L) => {
        if (cancelled || !containerRef.current) return;

        const map = new L.Map(containerRef.current, {
          key,
          maptype: "dreamy",
          center: [center.lat, center.lng],
          zoom,
          zoomSnap: 0.25,
          zoomControl: interactive,
          dragging: interactive,
          scrollWheelZoom: interactive,
          doubleClickZoom: interactive,
          boxZoom: interactive,
          keyboard: interactive,
          touchZoom: interactive,
        });

        mapRef.current = map;
        layerRef.current = L.layerGroup().addTo(map);

        if (interactive) {
          map.on("click", (event: any) => {
            clickRef.current?.({ lat: event.latlng.lat, lng: event.latlng.lng });
          });
        }

        const emitViewport = () => {
          if (viewportFrame.current) return;
          // moveend and zoomend usually fire together; coalescing them into one
          // frame keeps the cluster index from being queried twice per gesture.
          viewportFrame.current = window.requestAnimationFrame(() => {
            viewportFrame.current = 0;
            const bounds = map.getBounds();
            const current = map.getCenter();
            viewportRef.current?.({
              // Keep the fractional zoom: clustering floors it, but click-to-
              // expand needs to know how far the user has actually zoomed.
              zoom: map.getZoom(),
              center: { lat: current.lat, lng: current.lng },
              bbox: {
                west: bounds.getWest(),
                south: bounds.getSouth(),
                east: bounds.getEast(),
                north: bounds.getNorth(),
              },
            });
          });
        };
        map.on("moveend", emitViewport);
        map.on("zoomend", emitViewport);
        map.whenReady(() => emitViewport());

        setReady(true);
      })
      .catch(() => {
        if (!cancelled) setError("نقشه بارگذاری نشد. اتصال شبکه را بررسی کنید.");
      });

    return () => {
      cancelled = true;
      if (viewportFrame.current) {
        window.cancelAnimationFrame(viewportFrame.current);
        viewportFrame.current = 0;
      }
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      layerRef.current = null;
      pickerRef.current = null;
      fittedRef.current = false;
      setReady(false);
    };
    // Re-create only when the key changes; center/zoom/markers are synced below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    if (!mapRef.current || !ready) return;
    if (initialBounds && !fittedRef.current) {
      fittedRef.current = true;
      mapRef.current.fitBounds(initialBounds, { padding: [8, 8], maxZoom: 14 });
      return;
    }
    mapRef.current.setView([center.lat, center.lng], zoom);
  }, [center.lat, center.lng, zoom, ready, initialBounds]);

  // The map often mounts inside tabs/sheets whose width settles one frame
  // later. Without invalidateSize the tile pane can stay at the old size.
  useEffect(() => {
    if (!ready || !mapRef.current || !containerRef.current) return;
    const map = mapRef.current;
    const node = containerRef.current;
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(node);
    const frame = window.requestAnimationFrame(() => map.invalidateSize());
    return () => {
      observer.disconnect();
      window.cancelAnimationFrame(frame);
    };
  }, [ready]);

  useEffect(() => {
    if (!ready || !layerRef.current || !mapRef.current) return;
    const L = (window as Window & { L?: Leaflet }).L;
    if (!L) return;

    const layer = layerRef.current;
    layer.clearLayers();

    for (const marker of markers) {
      const color = marker.color ?? "#12b886";
      const icon =
        marker.count !== undefined
          ? clusterIcon(L, marker.count)
          : marker.compact
            ? dotIcon(L, color)
            : markerIcon(L, color, marker.offsetX, marker.offsetY);
      const instance = L.marker([marker.lat, marker.lng], {
        icon,
        title: marker.title ?? "",
        zIndexOffset: marker.count !== undefined ? 500 : marker.zIndexOffset ?? 0,
      });
      if (markerClickRef.current) {
        instance.on("click", () => markerClickRef.current?.(marker));
      } else {
        instance.bindPopup(popupElement(marker));
      }
      instance.addTo(layer);
    }

    if (fitToMarkers && markers.length > 0) {
      mapRef.current.invalidateSize();
      if (markers.length === 1) {
        mapRef.current.setView([markers[0].lat, markers[0].lng], 15);
      } else {
        const bounds = L.latLngBounds(markers.map((marker) => [marker.lat, marker.lng]));
        mapRef.current.fitBounds(bounds, { padding: [36, 36], maxZoom: 15 });
      }
    }
  }, [markers, fitToMarkers, ready]);

  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const L = (window as Window & { L?: Leaflet }).L;
    if (!L) return;

    if (!pickerMarker) {
      if (pickerRef.current) {
        pickerRef.current.remove();
        pickerRef.current = null;
      }
      return;
    }

    if (pickerRef.current) {
      pickerRef.current.setLatLng([pickerMarker.lat, pickerMarker.lng]);
      return;
    }

    const instance = L.marker([pickerMarker.lat, pickerMarker.lng], {
      icon: markerIcon(L, "#12b886"),
      draggable: true,
      autoPan: true,
    });
    instance.on("dragend", () => {
      const position = instance.getLatLng();
      pickerMoveRef.current?.({ lat: position.lat, lng: position.lng });
    });
    instance.addTo(mapRef.current);
    pickerRef.current = instance;
  }, [pickerMarker, ready]);

  return (
    <div className={cn("relative isolate z-0 overflow-hidden rounded-2xl bg-slate-100", className)}>
      <div ref={containerRef} className="h-full w-full" aria-label="نقشه نشان" role="application" />
      {!ready && !error && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-100 text-brand-600">
          <Spinner />
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-100 px-6 text-center">
          <p className="text-xs leading-6 text-slate-500">{error}</p>
        </div>
      )}
    </div>
  );
}
