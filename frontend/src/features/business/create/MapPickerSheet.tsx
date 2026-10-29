import { useCallback, useEffect, useState } from "react";

import { Button, Spinner } from "@/components/ui/button";
import { SearchIcon } from "@/components/ui/icons";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { NeshanMap } from "@/features/map/NeshanMap";
import type { Coordinates } from "@/types";

import { BEHBAHAN_CENTER } from "./types";

const ACCENT = "#12b886";

interface GeocodeResult {
  display_name: string;
  lat: number;
  lng: number;
  type?: string | null;
}

interface MapPickerSheetProps {
  open: boolean;
  address: string;
  value: Coordinates | null;
  onClose: () => void;
  onConfirm: (address: string, geo: Coordinates) => void;
}

function shortAddress(value: string): string {
  const first = value.split(",")[0]?.trim();
  return first || value;
}

function CloseIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      className="h-5 w-5"
      aria-hidden
    >
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}

function PinFilled({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M12 2a7.5 7.5 0 0 0-7.5 7.5c0 5.4 6.4 11.7 6.7 12a1.1 1.1 0 0 0 1.6 0c.3-.3 6.7-6.6 6.7-12A7.5 7.5 0 0 0 12 2Zm0 10.2a2.7 2.7 0 1 1 0-5.4 2.7 2.7 0 0 1 0 5.4Z" />
    </svg>
  );
}

function LocateIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      className={className}
      aria-hidden
    >
      <circle cx="12" cy="12" r="6.5" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
      <circle cx="12" cy="12" r="2" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function MapPickerSheet({ open, address, value, onClose, onConfirm }: MapPickerSheetProps) {
  const toast = useToast();
  const [query, setQuery] = useState(address);
  const [nearLabel, setNearLabel] = useState("موقعیت کسب‌وکار");
  const [resolvedAddress, setResolvedAddress] = useState("");
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [marker, setMarker] = useState<Coordinates | null>(value);
  const [center, setCenter] = useState<Coordinates>(value ?? BEHBAHAN_CENTER);
  const [zoom, setZoom] = useState(value ? 16 : 15);
  const [searching, setSearching] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(async (term: string) => {
    const text = term.trim();
    if (text.length < 3) {
      setError("برای جستجو حداقل ۳ نویسه از آدرس را وارد کنید.");
      return;
    }
    setSearching(true);
    setError(null);
    try {
      const data = await api<{ items: GeocodeResult[] }>(
        `/geo/search?q=${encodeURIComponent(text)}`,
      );
      setResults(data.items);
      if (data.items.length === 0) {
        setError("آدرسی با این متن پیدا نشد. عبارت دیگری امتحان کنید.");
        return;
      }
      const first = data.items[0];
      setMarker({ lat: first.lat, lng: first.lng });
      setCenter({ lat: first.lat, lng: first.lng });
      setZoom(16);
      setResolvedAddress(first.display_name);
      setNearLabel(`نزدیک ${shortAddress(first.display_name)}`);
    } catch (searchError) {
      setError(errorMessage(searchError));
    } finally {
      setSearching(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    setQuery(address);
    setMarker(value);
    setCenter(value ?? BEHBAHAN_CENTER);
    setZoom(value ? 16 : 15);
    setResults([]);
    setError(null);
    setResolvedAddress(address.trim());
    setNearLabel(
      address.trim() ? `نزدیک ${shortAddress(address)}` : "موقعیت کسب‌وکار",
    );
    if (!value && address.trim().length >= 3) void search(address);
    // Only re-initialise when the sheet opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  // Keep the address line in sync with the pin, like a map application.
  useEffect(() => {
    if (!open || !marker) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const resolved = await api<{ display_name: string }>(
          `/geo/reverse?lat=${marker.lat}&lng=${marker.lng}`,
        );
        if (cancelled) return;
        setResolvedAddress(resolved.display_name);
        setNearLabel(`نزدیک ${shortAddress(resolved.display_name)}`);
      } catch {
        if (!cancelled) setNearLabel("موقعیت انتخاب‌شده");
      }
    }, 650);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [marker, open]);

  function pick(result: GeocodeResult) {
    setMarker({ lat: result.lat, lng: result.lng });
    setCenter({ lat: result.lat, lng: result.lng });
    setZoom(16);
    setQuery(result.display_name);
    setResolvedAddress(result.display_name);
    setNearLabel(`نزدیک ${shortAddress(result.display_name)}`);
  }

  function useMyLocation() {
    if (!navigator.geolocation) {
      toast("مرورگر شما از موقعیت مکانی پشتیبانی نمی‌کند.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const next = { lat: position.coords.latitude, lng: position.coords.longitude };
        setMarker(next);
        setCenter(next);
        setZoom(16);
      },
      () => toast("دسترسی به موقعیت مکانی ممکن نشد."),
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  }

  function confirm() {
    if (!marker) {
      toast("ابتدا موقعیت کسب‌وکار را روی نقشه انتخاب کنید.");
      return;
    }
    setConfirming(true);
    // Preserve what the owner typed; reverse geocoding is only a fallback.
    const finalAddress = query.trim() || resolvedAddress.trim() || address;
    onConfirm(finalAddress, marker);
    setConfirming(false);
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-200">
      <div className="absolute inset-0 z-0">
        <NeshanMap
          center={center}
          zoom={zoom}
          className="nomax-picker-map h-full w-full rounded-none"
          pickerMarker={marker}
          onPickerMove={(coords) => setMarker(coords)}
          onMapClick={(coords) => setMarker(coords)}
        />
      </div>

      <div className="pointer-events-none absolute inset-x-0 top-0 z-30 grid grid-cols-[44px_1fr_44px] items-start gap-2 p-4">
        <button
          type="button"
          onClick={onClose}
          aria-label="بستن نقشه"
          className="pointer-events-auto flex h-11 w-11 items-center justify-center rounded-full bg-white text-slate-700 shadow-lg shadow-slate-900/20"
        >
          <CloseIcon />
        </button>
        <div className="pointer-events-auto mx-auto rounded-full bg-white px-6 py-3 text-base font-bold text-slate-900 shadow-lg shadow-slate-900/20">
          موقعیت کسب‌وکار
        </div>
        <span aria-hidden />
      </div>

      <div className="absolute inset-x-0 bottom-0 z-30 rounded-t-[28px] bg-white px-4 pb-5 pt-2 shadow-[0_-12px_44px_-14px_rgba(15,23,42,0.35)] safe-bottom">
        <button
          type="button"
          onClick={useMyLocation}
          aria-label="موقعیت فعلی من"
          className="absolute -top-16 right-4 flex h-11 w-11 items-center justify-center rounded-full bg-white text-[#12b886] shadow-lg shadow-slate-900/20"
        >
          <LocateIcon className="h-6 w-6" />
        </button>

        <div className="mx-auto mb-3 h-1.5 w-10 rounded-full bg-slate-200" />

        <div className="flex items-center justify-end gap-1.5">
          <PinFilled className="h-4 w-4 shrink-0 text-rose-500" />
          <span className="truncate text-[11px] font-medium text-slate-500">{nearLabel}</span>
        </div>

        <div className="relative mt-3">
          <button
            type="button"
            onClick={() => void search(query)}
            aria-label="جستجوی آدرس"
            className="absolute right-1 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full text-slate-600"
          >
            {searching ? <Spinner /> : <SearchIcon className="h-5 w-5" />}
          </button>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void search(query);
              }
            }}
            placeholder="جستجوی آدرس..."
            className="h-12 w-full rounded-2xl bg-slate-100 pr-12 pl-12 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#12b886]/40"
          />
          {query && (
            <button
              type="button"
              onClick={() => {
                setQuery("");
                setResults([]);
                setError(null);
              }}
              aria-label="پاک کردن جستجو"
              className="absolute left-1 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full bg-slate-200 text-sm text-slate-500"
            >
              ×
            </button>
          )}
        </div>

        {results.length > 1 && (
          <div className="mt-2 flex gap-1.5 overflow-x-auto pb-1">
            {results.map((result, index) => (
              <button
                key={`${result.lat}-${result.lng}-${index}`}
                type="button"
                onClick={() => pick(result)}
                className={cn(
                  "max-w-[220px] shrink-0 truncate rounded-full border px-3 py-1.5 text-[11px]",
                  marker?.lat === result.lat && marker?.lng === result.lng
                    ? "border-[#12b886]/40 bg-[#12b886]/10 text-[#0b8a5c]"
                    : "border-slate-200 bg-white text-slate-500",
                )}
                title={result.display_name}
              >
                {result.display_name}
              </button>
            ))}
          </div>
        )}

        {error && <p className="mt-2 text-[11px] leading-5 text-rose-600">{error}</p>}

        <Button
          type="button"
          onClick={confirm}
          loading={confirming}
          className="mt-4 h-12 w-full rounded-2xl text-base font-bold text-white"
          style={{ backgroundColor: ACCENT }}
        >
          تأیید موقعیت
        </Button>
        <p className="mt-2 text-center text-[9px] text-slate-400">
          © Neshan · © OpenStreetMap contributors
        </p>
      </div>
    </div>
  );
}
