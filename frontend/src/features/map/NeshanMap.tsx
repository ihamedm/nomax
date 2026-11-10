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
  /**
   * Marker shape. `dot` (default) is the small round pin used in feeds;
   * `pushpin` is the taller teardrop marker used to highlight one place.
   */
  variant?: "dot" | "pushpin";
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
  picker = false,
  color?: string,
  offsetX = 0,
  offsetY = 0,
  variant: "dot" | "pushpin" = "dot",
) {
  // The picker and pushpin markers have a circular head plus a tail, so they
  // need a larger canvas and their anchor sits at the tip of the tail.
  const tail = picker || variant === "pushpin";
  const styles = [
    color ? `background:${color}` : "",
    offsetX || offsetY ? `position:relative;left:${offsetX}px;top:${offsetY}px` : "",
  ]
    .filter(Boolean)
    .join(";");
  const colorStyle = styles ? ` style="${styles}"` : "";
  const modifier = picker
    ? " nomax-map-pin--picker"
    : variant === "pushpin"
      ? " nomax-map-pin--pushpin"
      : "";
  return L.divIcon({
    className: "",
    html: `<span class="nomax-map-pin${modifier}"${colorStyle}></span>`,
    iconSize: picker ? [46, 58] : tail ? [36, 46] : [24, 24],
    iconAnchor: picker ? [23, 56] : tail ? [16, 42] : [12, 12],
    popupAnchor: [0, -14],
  });
}

function clusterIcon(L: Leaflet, count: number) {
  const size = count >= 100 ? 56 : count >= 10 ? 46 : 38;
  const label = count.toLocaleString("fa-IR", { useGrouping: false });
  return L.divIcon({
    className: "",
    html: `<span class="nomax-map-cluster" style="width:${size}px;height:${size}px;font-size:${
      count >= 100 ? 12 : 13
    }px">${label}</span>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
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
  const clickRef = useRef(onMapClick);
  const markerClickRef = useRef(onMarkerClick);
  const pickerMoveRef = useRef(onPickerMove);
  const viewportRef = useRef(onViewportChange);
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
      setError("کلید نقشه تنظیم نشده است. مقدار VITE_NESHAN_MAP_KEY را در محیط تنظیم کنید.");
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
          const bounds = map.getBounds();
          const current = map.getCenter();
          viewportRef.current?.({
            zoom: Math.round(map.getZoom()),
            center: { lat: current.lat, lng: current.lng },
            bbox: {
              west: bounds.getWest(),
              south: bounds.getSouth(),
              east: bounds.getEast(),
              north: bounds.getNorth(),
            },
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
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      layerRef.current = null;
      pickerRef.current = null;
      setReady(false);
    };
    // Re-create only when the key changes; center/zoom/markers are synced below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    if (!mapRef.current || !ready) return;
    mapRef.current.setView([center.lat, center.lng], zoom);
  }, [center.lat, center.lng, zoom, ready]);

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
      const instance = L.marker([marker.lat, marker.lng], {
        icon:
          marker.count !== undefined
            ? clusterIcon(L, marker.count)
            : markerIcon(
                L,
                false,
                marker.color,
                marker.offsetX,
                marker.offsetY,
                marker.variant,
              ),
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
      icon: markerIcon(L, true),
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
