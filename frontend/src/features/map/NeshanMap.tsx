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
}

interface NeshanMapProps {
  center: Coordinates;
  zoom?: number;
  markers?: MapMarker[];
  className?: string;
  interactive?: boolean;
  fitToMarkers?: boolean;
  onMapClick?: (coords: Coordinates) => void;
  pickerMarker?: Coordinates | null;
  onPickerMove?: (coords: Coordinates) => void;
}

// The Neshan SDK is a UMD Leaflet build; its types live outside our bundle.
type Leaflet = Record<string, any>;

function markerIcon(L: Leaflet, picker = false) {
  // The picker pin has a circular head plus a tail, so it needs a larger
  // canvas and its anchor sits at the tip of the tail.
  return L.divIcon({
    className: "",
    html: `<span class="nomax-map-pin${picker ? " nomax-map-pin--picker" : ""}"></span>`,
    iconSize: picker ? [46, 58] : [24, 24],
    iconAnchor: picker ? [23, 56] : [12, 12],
    popupAnchor: [0, -14],
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
  pickerMarker,
  onPickerMove,
}: NeshanMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>(null);
  const layerRef = useRef<any>(null);
  const pickerRef = useRef<any>(null);
  const clickRef = useRef(onMapClick);
  const pickerMoveRef = useRef(onPickerMove);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  clickRef.current = onMapClick;
  pickerMoveRef.current = onPickerMove;

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

  useEffect(() => {
    if (!ready || !layerRef.current || !mapRef.current) return;
    const L = (window as Window & { L?: Leaflet }).L;
    if (!L) return;

    const layer = layerRef.current;
    layer.clearLayers();

    for (const marker of markers) {
      const instance = L.marker([marker.lat, marker.lng], {
        icon: markerIcon(L),
        title: marker.title ?? "",
      });
      instance.bindPopup(popupElement(marker));
      instance.addTo(layer);
    }

    if (fitToMarkers && markers.length > 0) {
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
