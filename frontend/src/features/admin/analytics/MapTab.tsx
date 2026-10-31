import { useMemo, useState } from "react";

import { cn } from "@/lib/cn";
import { toFa } from "@/lib/digits";
import { NeshanMap, type MapMarker } from "@/features/map/NeshanMap";
import type { AnalyticsMapData } from "./types";

const COLORS = {
  business: "#0b8a5c",
  quote: "#0284c7",
  urgent: "#e11d48",
} as const;

type Layer = keyof typeof COLORS;

const LAYER_LABELS: Record<Layer, string> = {
  business: "کسب‌وکار",
  quote: "استعلام",
  urgent: "استعلام فوری",
};

export function MapTab({ data }: { data: AnalyticsMapData }) {
  const [fitAll, setFitAll] = useState(false);
  const [visible, setVisible] = useState<Record<Layer, boolean>>({
    business: true,
    quote: true,
    urgent: true,
  });

  const markers = useMemo<MapMarker[]>(() => {
    const businessMarkers: MapMarker[] = visible.business
      ? data.businesses.map((business) => ({
          id: `business:${business.id}`,
          lat: business.lat,
          lng: business.lng,
          title: business.name,
          subtitle: `${business.category_icon} ${business.category_name}`,
          color: COLORS.business,
        }))
      : [];
    const quoteMarkers: MapMarker[] = visible.quote
      ? data.quotes.map((quote) => ({
          id: `quote:${quote.id}`,
          lat: quote.lat,
          lng: quote.lng,
          title: quote.title,
          subtitle: `${quote.category_name} · درخواست قیمت`,
          color: COLORS.quote,
          zIndexOffset: 1000,
          offsetX: 13,
          offsetY: -10,
        }))
      : [];
    const urgentMarkers: MapMarker[] = visible.urgent
      ? data.urgent_quotes.map((quote) => ({
          id: `urgent:${quote.id}`,
          lat: quote.lat,
          lng: quote.lng,
          title: `⚡ ${quote.title}`,
          subtitle: `${quote.category_name} · درخواست فوری`,
          color: COLORS.urgent,
          zIndexOffset: 2000,
          offsetX: -13,
          offsetY: -10,
        }))
      : [];
    return [...businessMarkers, ...quoteMarkers, ...urgentMarkers];
  }, [data, visible]);

  const counts: Record<Layer, number> = {
    business: data.businesses.length,
    quote: data.quotes.length,
    urgent: data.urgent_quotes.length,
  };
  const total = counts.business + counts.quote + counts.urgent;

  return (
    <div className="relative h-[calc(100dvh-13rem)] min-h-[480px] overflow-hidden rounded-2xl border border-slate-200 bg-slate-100">
      <NeshanMap
        center={{ lat: 30.638, lng: 50.838 }}
        zoom={13}
        className="h-full w-full rounded-none"
        markers={markers}
        fitToMarkers={fitAll}
      />

      <div className="absolute right-3 top-3 z-20 w-56 rounded-2xl border border-slate-200 bg-white/95 p-3 shadow-lg backdrop-blur">
        <div className="flex items-center justify-between">
          <p className="text-xs font-black text-slate-900">نقشه بازار</p>
          <span className="text-[10px] text-slate-400">{toFa(total)} نقطه</span>
        </div>
        <p className="mt-1 text-[9px] leading-4 text-slate-400">
          کسب‌وکارهای تأییدشده و استعلام‌های فعال. برای پنهان‌کردن هر لایه کلیک کنید.
        </p>
        <div className="mt-2 space-y-1">
          {(Object.keys(COLORS) as Layer[]).map((layer) => (
            <button
              key={layer}
              type="button"
              onClick={() =>
                setVisible((current) => ({ ...current, [layer]: !current[layer] }))
              }
              className={cn(
                "flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-[10px] transition-colors",
                visible[layer] ? "bg-slate-50 text-slate-700" : "text-slate-400",
              )}
            >
              <span className="flex items-center gap-1.5">
                <span
                  className={cn("h-2.5 w-2.5 rounded-full", !visible[layer] && "opacity-30")}
                  style={{ backgroundColor: COLORS[layer] }}
                />
                {LAYER_LABELS[layer]}
              </span>
              <span className={cn("font-bold", !visible[layer] && "line-through")}>
                {toFa(counts[layer])}
              </span>
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setFitAll(true)}
          className="mt-2 w-full rounded-lg border border-slate-200 px-2 py-1.5 text-[10px] text-slate-500 hover:border-brand-300 hover:text-brand-700"
        >
          نمایش همه نقاط روی نقشه
        </button>
      </div>

      {total === 0 && (
        <div className="pointer-events-none absolute inset-x-0 bottom-5 z-20 flex justify-center">
          <span className="rounded-full bg-white/95 px-4 py-2 text-[11px] text-slate-500 shadow">
            هنوز نقطه‌ای برای نمایش روی نقشه ثبت نشده است.
          </span>
        </div>
      )}
    </div>
  );
}
